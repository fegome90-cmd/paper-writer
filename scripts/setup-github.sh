#!/usr/bin/env bash
set -euo pipefail

EM_DASH=$'—'

# ---------------------------------------------------------------------------
# Preflight: verify bash, gh, jq, authentication, and admin permissions
# ---------------------------------------------------------------------------
check_admin() {
  if [ -z "${BASH_VERSION:-}" ]; then
    printf "  ERROR: Not running under bash\n" >&2
    return 1
  fi

  if ! command -v gh >/dev/null 2>&1; then
    printf "  ERROR: 'gh' CLI not found. Install: https://cli.github.com\n" >&2
    return 1
  fi

  if ! command -v jq >/dev/null 2>&1; then
    printf "  ERROR: 'jq' not found. Install: https://stedolan.github.io/jq\n" >&2
    return 1
  fi

  local user
  user=$(gh api user --jq '.login') || {
    printf "  ERROR: gh not authenticated. Run: gh auth login\n" >&2
    return 1
  }

  local perms
  perms=$(gh api "repos/${REPO}" --jq '.permissions.admin') || {
    printf "  ERROR: Cannot read repository permissions\n" >&2
    return 1
  }
  if [ "$perms" != "true" ]; then
    printf "  ERROR: Admin access required. Current permissions lack .admin=true\n" >&2
    return 1
  fi

  printf "  OK: bash, gh, jq available\n"
  printf "  OK: gh authenticated as %s\n" "$user"
  printf "  OK: Admin access confirmed\n"
}

# ---------------------------------------------------------------------------
# Detect the repo in owner/name format
# ---------------------------------------------------------------------------
detect_repo() {
  gh repo view --json nameWithOwner --jq '.nameWithOwner'
}

# ---------------------------------------------------------------------------
# Enable secret scanning and push protection via PATCH
# ---------------------------------------------------------------------------
configure_security() {
  local body
  body=$(jq -n '{
    security_and_analysis: {
      secret_scanning: { status: "enabled" },
      push_protection:  { status: "enabled" }
    }
  }')

  local response
  response=$(gh api "repos/${REPO}" --method PATCH --input - <<<"$body" 2>&1) || {
    printf "  ERROR: Failed to PATCH security settings: %s\n" "$response" >&2
    return 1
  }

  # Verify the settings actually took effect from the PATCH response
  local scanning push
  scanning=$(echo "$response" | jq -r '.security_and_analysis.secret_scanning.status // "QUERY FAILED"')
  push=$(echo "$response" | jq -r '.security_and_analysis.push_protection.status // "QUERY FAILED"')

  if [ "$scanning" != "enabled" ]; then
    printf "  WARN: secret_scanning is '%s' after PATCH (org-level config may override)\n" "$scanning"
  else
    printf "  OK: Secret scanning enabled\n"
  fi

  if [ "$push" != "enabled" ]; then
    printf "  WARN: push_protection is '%s' after PATCH (org-level config may override)\n" "$push"
  else
    printf "  OK: Push protection enabled\n"
  fi
}

# ---------------------------------------------------------------------------
# Validate that required check names exist in real CI runs for CHECKS_SHA
# ---------------------------------------------------------------------------
validate_required_checks() {
  if [ "${ENFORCE_CHECKS:-0}" != "1" ]; then
    return 0
  fi

  if [ -z "${CHECKS_SHA:-}" ]; then
    printf "  ERROR: ENFORCE_CHECKS=1 requires CHECKS_SHA to be set\n" >&2
    return 1
  fi

  local expected_checks
  expected_checks=$(build_check_names_json)

  local actual_checks
  actual_checks=$(gh api "repos/${REPO}/commits/${CHECKS_SHA}/check-runs" \
    --paginate --jq '.check_runs[].name') || {
    printf "  ERROR: Cannot fetch check-runs for SHA %s\n" "$CHECKS_SHA" >&2
    return 1
  }

  local missing=0
  while IFS= read -r check_name; do
    if ! echo "$actual_checks" | grep -qF -- "$check_name"; then
      printf "  ERROR: Required check not found in CI: '%s'\n" "$check_name" >&2
      missing=$((missing + 1))
    fi
  done < <(echo "$expected_checks" | jq -r '.[]')

  if [ "$missing" -gt 0 ]; then
    printf "  ERROR: %d required check(s) missing. Fix CI before enabling enforcement.\n" "$missing" >&2
    return 1
  fi

  printf "  OK: All %d required checks found in CI\n" "$(echo "$expected_checks" | jq 'length')"
}

# ---------------------------------------------------------------------------
# Build rules JSON array (profile-dependent base rules + optional checks)
# Profile-dependent rules: solo (default) or team. Phase 2 adds required_status_checks.
# ---------------------------------------------------------------------------
build_rules_json() {
  local profile="${RULESET_PROFILE:-solo}"
  if [ "$profile" != "solo" ] && [ "$profile" != "team" ]; then
    printf "  ERROR: RULESET_PROFILE must be 'solo' or 'team', got '%s'\n" "$profile" >&2
    return 1
  fi
  local review_count=0 code_owner=false last_push=false

  if [ "$profile" = "team" ]; then
    review_count=1
    code_owner=true
    last_push=true
  fi

  local rules
  rules=$(jq -n \
    --argjson review_count "$review_count" \
    --argjson code_owner "$code_owner" \
    --argjson last_push "$last_push" \
    '[
      {"type": "pull_request", "parameters": {
        "required_approving_review_count": $review_count,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": $code_owner,
        "require_last_push_approval": $last_push,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["squash"]
      }},
      {"type": "required_linear_history"},
      {"type": "non_fast_forward"},
      {"type": "deletion"}
    ]')

  # Phase 2: append required_status_checks
  if [ "${ENFORCE_CHECKS:-0}" = "1" ]; then
    local check_names status_check_rule
    check_names=$(build_check_names_json)
    status_check_rule=$(jq -n \
      --argjson checks "$check_names" \
      '{"type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": ($checks | map({context: .}))
      }}')
    rules=$(echo "$rules" | jq --argjson scr "$status_check_rule" '. + [$scr]')
  fi

  echo "$rules"
}

# ---------------------------------------------------------------------------
# Build the standard check names JSON array (with em-dash U+2014)
# Source of truth: .github/workflows/ci.yml job names
# Keep in sync with .github/workflows/ci.yml and .github/workflows/security.yml
# ---------------------------------------------------------------------------
build_check_names_json() {
  jq -n --arg em "$EM_DASH" '[
    "Quality",
    ("Core tests " + $em + " Python 3.10"),
    ("Core tests " + $em + " Python 3.12"),
    ("Core tests " + $em + " Python 3.13"),
    ("Local skills " + $em + " thesaurus + MeSH import"),
    "Offline E2E",
    "Build and install smoke test",
    "Dependency review",
    "Python dependency audit",
    "CodeQL"
  ]'
}

# ---------------------------------------------------------------------------
# Upsert branch ruleset: POST if new, PUT if existing
# ---------------------------------------------------------------------------
configure_ruleset() {
  local rules
  rules=$(build_rules_json)

  local payload
  payload=$(jq -n --argjson rules "$rules" '{
    "name": "main-branch-protection",
    "target": "branch",
    "enforcement": "active",
    "conditions": {
      "ref_name": {
        "include": ["~DEFAULT_BRANCH"],
        "exclude": []
      }
    },
    "rules": $rules
  }')

  # Check for existing repo-level ruleset
  local existing=""
  if existing=$(gh api "repos/${REPO}/rulesets?includes_parents=false" \
    --jq '.[] | select(.name=="main-branch-protection" and .source_type=="Repository") | .id' 2>&1); then
    : # success - existing may be empty (no match) or contain an ID
  else
    printf "  ERROR: Failed to query rulesets: %s\n" "$existing" >&2
    return 1
  fi

  if [ -n "$existing" ]; then
    local put_err
    put_err=$(gh api "repos/${REPO}/rulesets/${existing}" --method PUT --input - <<<"$payload" 2>&1) || {
      printf "  ERROR: Failed to PUT ruleset %s: %s\n" "$existing" "$put_err" >&2
      return 1
    }
    printf "  OK: Upserted ruleset 'main-branch-protection' (PUT)\n"
  else
    local post_err
    post_err=$(gh api "repos/${REPO}/rulesets" --method POST --input - <<<"$payload" 2>&1) || {
      printf "  ERROR: Failed to POST ruleset: %s\n" "$post_err" >&2
      return 1
    }
    printf "  OK: Upserted ruleset 'main-branch-protection' (POST)\n"
  fi
}

# ---------------------------------------------------------------------------
# Create/update the live-integrations environment (PUT is idempotent)
# ---------------------------------------------------------------------------
configure_environment() {
  local env_err
  env_err=$(gh api "repos/${REPO}/environments/live-integrations" --method PUT 2>&1) || {
    printf "  ERROR: Failed to configure environment 'live-integrations': %s\n" "$env_err" >&2
    return 1
  }
  printf "  OK: Environment configured\n"
}

# ---------------------------------------------------------------------------
# Set a single secret; skip with warning if env var is not set
# ---------------------------------------------------------------------------
set_secret() {
  local env_var="$1"
  local secret_name="$2"
  if [ -n "${!env_var:-}" ]; then
    printf '%s' "${!env_var}" | gh secret set "$secret_name" --env live-integrations --repo "${REPO}" --silent
    printf "  OK: Updated %s\n" "$secret_name"
  else
    printf "  WARN: %s not set, skipping\n" "$env_var" >&2
  fi
}

# ---------------------------------------------------------------------------
# Set Zotero secrets (always update for rotation; skip if env vars missing)
# ---------------------------------------------------------------------------
configure_secrets() {
  printf "Setting secrets...\n"
  set_secret "ZOTERO_USER_ID" "ZOTERO_USER_ID"
  set_secret "ZOTERO_API_KEY" "ZOTERO_API_KEY"
}

# ---------------------------------------------------------------------------
# Post-run verification of all configured settings
# ---------------------------------------------------------------------------
verify_configuration() {
  printf "\n=== Verification ===\n"
  local verify_errors=0

  # Ruleset
  local rule_count
  rule_count=$(gh api "repos/${REPO}/rulesets?includes_parents=false" \
    --jq '[.[] | select(.name=="main-branch-protection") | .rules | length] | .[0]' 2>&1) || {
    printf "  Ruleset: QUERY FAILED (%s)\n" "$rule_count"
    verify_errors=$((verify_errors + 1))
    rule_count=""
  }
  if [ -n "$rule_count" ]; then
    printf "  Ruleset: main-branch-protection (active, %s rules)\n" "$rule_count"
  fi

  # Environment
  local env_status
  env_status=$(gh api "repos/${REPO}/environments/live-integrations" --jq '.name' 2>&1) || {
    printf "  Environment: live-integrations NOT found (%s)\n" "$env_status"
    verify_errors=$((verify_errors + 1))
    env_status=""
  }
  if [ -n "$env_status" ]; then
    printf "  Environment: live-integrations confirmed\n"
  fi

  # Secrets (only report those actually set)
  local secret_list=()
  if [ -n "${ZOTERO_USER_ID:-}" ]; then
    secret_list+=("ZOTERO_USER_ID")
  fi
  if [ -n "${ZOTERO_API_KEY:-}" ]; then
    secret_list+=("ZOTERO_API_KEY")
  fi
  if [ ${#secret_list[@]} -gt 0 ]; then
    printf "  Secrets: %s\n" "$(IFS=, ; echo "${secret_list[*]}")"
  else
    printf "  Secrets: none set (ZOTERO_USER_ID and ZOTERO_API_KEY not in environment)\n"
  fi

  if [ "$verify_errors" -gt 0 ]; then
    printf "  WARNING: %d verification check(s) failed\n" "$verify_errors" >&2
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
main() {
  REPO=$(detect_repo)
  if [ -z "$REPO" ]; then
    printf "ERROR: Could not detect repository. Are you in a git repo with a GitHub remote?\n" >&2
    exit 1
  fi
  readonly REPO

  printf "\n=== Configuring %s ===\n\n" "$REPO"

  printf "[1/5] Preflight checks\n"
  check_admin || return 1

  printf "\n[2/5] Security scanning + push protection\n"
  configure_security || return 1

  printf "\n[3/5] Branch ruleset for main (profile: %s)\n" "${RULESET_PROFILE:-solo}"
  validate_required_checks || return 1
  configure_ruleset || return 1

  printf "\n[4/5] Environment 'live-integrations'\n"
  configure_environment || return 1

  printf "\n[5/5] Zotero secrets\n"
  configure_secrets || return 1

  local verify_rc=0
  verify_configuration || verify_rc=$?
  printf "\n=== Done ===\n"
  return $verify_rc
}

main "$@"
