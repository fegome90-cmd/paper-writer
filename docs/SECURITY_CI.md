# Security CI — Dependency Graph, Dependabot, and the Preflight Job

This document explains the official GitHub mechanisms used by the `security.yml`
workflow and the `scripts/setup-github.sh` bootstrap to keep `dependency-review`
green. It is the reference linked by the pinned fail messages emitted by the
`repo-config-preflight` job.

> **Accuracy note**: every enable mechanism below was verified against official
> GitHub REST API documentation via context7 (see SDD artifact
> `sdd/security-ci-hardening/context7-verify`). The two `security_and_analysis`
> sub-fields discussed are NOT documented PATCH setters — only the dedicated
> endpoints are.

---

## 1. Official enable mechanisms

### Dependency graph — `PUT /repos/{owner}/{repo}/vulnerability-alerts`

The dependency graph is enabled (and dependency alerts turned on) via the
dedicated endpoint:

```bash
gh api -X PUT repos/{owner}/{repo}/vulnerability-alerts   # enable
gh api -X DELETE repos/{owner}/{repo}/vulnerability-alerts # disable
```

Returns `204` on success. Requires **Administration: write**.

> **Do NOT use** `PATCH /repos/{owner}/{repo}` with
> `security_and_analysis[dependency_graph][status]=enabled`. That field appears
> in `GET` responses but is **not a documented PATCH setter**. The dedicated
> `/vulnerability-alerts` endpoint is the canonical enable path.

### Dependabot security updates — `PUT /repos/{owner}/{repo}/automated-security-fixes`

Dependabot security updates are enabled via their dedicated endpoint:

```bash
gh api -X PUT repos/{owner}/{repo}/automated-security-fixes    # enable
gh api -X DELETE repos/{owner}/{repo}/automated-security-fixes # disable
gh api repos/{owner}/{repo}/automated-security-fixes           # check status (GET)
```

Requires **Administration: write**.

> **Do NOT use** `PATCH /repos/{owner}/{repo}` with
> `security_and_analysis[dependabot_security_updates][status]=enabled`. As with
> the dependency graph, that field appears in `GET` responses (since a July 2023
> changelog) but is **not a documented PATCH setter**. The dedicated
> `/automated-security-fixes` endpoint is the canonical enable path.

Both PUTs are performed by `configure_dependency_graph()` in
`scripts/setup-github.sh`, gated behind the existing `check_admin` precondition.

---

## 2. The SBOM exit-code probe

The `repo-config-preflight` job in `.github/workflows/security.yml` probes the
dependency graph by **exit code**, not HTTP status flag:

```bash
gh api repos/${{ github.repository }}/dependency-graph/sbom >/dev/null 2>&1
```

| HTTP status | Exit code | Meaning | Preflight action |
|-------------|-----------|---------|------------------|
| `200`       | `0`       | Graph ready | succeed, `dependency-review` runs |
| `403`       | non-zero  | Permission gap (`contents: read` insufficient) | FAIL — pinned permission-gap message (add Administration-scoped token) |
| `404`       | non-zero  | Dependency graph is disabled | FAIL — pinned message (`PUT .../vulnerability-alerts`, then re-run) |
| other       | non-zero  | Unexpected status (transient GitHub error, runner network issue, or rate limit) | FAIL — **do NOT change config**; re-run the workflow first |

To distinguish 403 (permission gap) from 404 (graph off), the job re-probes with
`gh api -i` and inspects the HTTP status line, routing each status to a distinct
pinned message. Any status other than 200 / 403 / 404 (e.g. 401, 429, 5xx, or
`000` on a network failure) is treated as unexpected: the preflight fails but
advises re-running the workflow before changing any repository config, since the
remediations for 403 or 404 do not address those cases.

> **The `-w '%{http_code}'` curl flag is NOT valid for `gh`.** `gh` silently
> ignores it. Branch on the exit code instead. This is a pinned load-bearing
> decision in the SDD spec.

---

## 3. Enterprise / private repository `permissions:` caveat

On private or enterprise-managed repositories, the default `GITHUB_TOKEN` may
need additional `permissions:` to read the SBOM. If the preflight fails on a
private/enterprise repo with 403, admins should:

1. Verify the workflow-level and job-level `permissions:` block in
   `.github/workflows/security.yml`.
2. Check whether an enterprise policy restricts dependency-graph reads.
3. If `contents: read` proves insufficient (see C7 below), supply an
   Administration-scoped token (Administration: read) to the preflight job.

---

## 4. C7 — `contents: read` sufficiency for the SBOM endpoint is UNDOCUMENTED

GitHub **does not document** `permissions: contents: read` as sufficient for
`GET /repos/{owner}/{repo}/dependency-graph/sbom`. Related dependency-graph
endpoints require the **Administration** permission. The preflight job therefore
declares `permissions: contents: read` (matching the other jobs in
`security.yml`), but this assumption was **empirically verified in CI** rather
than taken on faith.

**Verification outcome (C7 probe)**: Empirically verified once via a one-off
CI probe (GitHub Actions run 28027282132, 2026-06-23): under a token scoped
**only** to `permissions: contents: read`, `gh api .../dependency-graph/sbom`
returned **200** (SPDX-2.3) on this repository. The assumption holds;
`contents: read` is sufficient here. No Administration-scoped token is required
for the preflight.

If a future change to the repository's visibility, enterprise policy, or
GitHub's permission model causes the probe to return **403**, the preflight will
fail loudly with the pinned permission-gap message (it will **never** silently
pass). On 403, the fix is to add an Administration-scoped token
(Administration: read) to the preflight job and update this section with the new
evidence. Do not claim `contents: read` is sufficient without empirical proof.

---

## 5. Drift detection

The expected CI check names are pinned in `.github/expected-checks.json` (single
source of truth). A dedicated lint workflow
(`.github/workflows/check-names-lint.yml`) extracts the `name:` values declared
under `jobs:` in both `.github/workflows/ci.yml` and
`.github/workflows/security.yml` and diffs the sorted set against the JSON. The
workflow fails on mismatch, catching drift when a job is added or renamed.
