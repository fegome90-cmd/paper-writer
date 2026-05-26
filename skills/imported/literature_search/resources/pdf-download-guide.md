---
version: 1.0.0
updated: 2026-05-22
purpose: PDF download strategy with paywall detection and fallback chain
---

# PDF Download Guide — Literature Search Skill

## Sources That Work (CLI curl)

These sources provide direct PDF downloads without authentication.

### ✅ PLOS ONE

```bash
curl -sL -o "paper.pdf" \
  "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.XXXXXXX&type=printable" \
  -H "User-Agent: Mozilla/5.0" --max-time 30
```

**Verify:** `head -c 5 paper.pdf` → should be `%PDF-`

### ✅ BMC / BioMed Central

```bash
curl -sL -o "paper.pdf" \
  "https://bmccancer.biomedcentral.com/counter/pdf/10.1186/s12885-XXX-XXXX-X.pdf" \
  -H "User-Agent: Mozilla/5.0" --max-time 30
```

Other BMC journals:
- `bmchealthservres.biomedcentral.com`
- `bmcmedicine.biomedcentral.com`
- `bmjopen.bmj.com` (BMJ Open)

### ✅ Springer Open Access

```bash
curl -sL -o "paper.pdf" \
  "https://link.springer.com/content/pdf/10.1186/s12955-XXX-XXXX-X.pdf" \
  -H "User-Agent: Mozilla/5.0" --max-time 30
```

### ✅ UCL Discovery (Theses)

```bash
curl -sL -o "thesis.pdf" \
  "https://discovery.ucl.ac.uk/ID/ID/Thesis.pdf" \
  -H "User-Agent: Mozilla/5.0" --max-time 30
```

## Sources That DON'T Work (Paywall/Bot Detection)

| Publisher | Status | Workaround |
|-----------|--------|------------|
| **Elsevier/ScienceDirect** | ❌ 403 | Institutional access |
| **JAMA Network** | ❌ HTML redirect | Institutional access |
| **Wiley** | ❌ 403 | Institutional access |
| **Oxford Academic** | ❌ 403 | Institutional access |
| **MDPI** | ❌ 403 | Institutional access |
| **JMIR** | ❌ 405/HTML | HTML available, no PDF |
| **Europe PMC** | ❌ Connection refused | Blocked from CLI |
| **PMC direct PDF** | ❌ HTML | Use full text instead |

## Verification Protocol

After every download:

```bash
header=$(head -c 5 "paper.pdf")
if [[ "$header" == "%PDF-" ]]; then
  echo "✅ Valid PDF"
else
  echo "❌ Not a PDF (got: $header)"
  rm -f "paper.pdf"
fi
```

## Fallback Strategy

When PDF is not available:

1. **PMC full text (HTML)** — Extract all data from HTML version. This is the **primary fallback** — contains complete abstract, methods, results, tables, and figures. Structured extraction works well via `web_fetch`.
2. **PubMed abstract** — Get abstract + metadata (limited but sufficient for scoring)
3. **Journal website** — Read via browser automation if critical
4. **Preprint servers** — Check arXiv, medRxiv, bioRxiv
5. **Author pages** — Sometimes authors post free PDFs on institutional sites

> **Key distinction:** PMC HTML full text ≠ PMC PDF. The HTML version is always accessible for open-access articles and contains 100% of the data needed for extraction. PDF is a convenience format for offline reading, not required for the skill workflow.

## Batch Download Template

```bash
#!/bin/bash
# Batch PDF downloader for open access papers
# Usage: ./download-pdfs.sh urls.txt

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
OUTPUT_DIR="pdfs"
mkdir -p "$OUTPUT_DIR"

while IFS='|' read -r name url; do
  echo -n "Downloading $name... "
  curl -sL -o "${OUTPUT_DIR}/${name}.pdf" "$url" \
    -H "User-Agent: $UA" --max-time 30
  
  header=$(head -c 5 "${OUTPUT_DIR}/${name}.pdf" 2>/dev/null)
  if [[ "$header" == "%PDF-" ]]; then
    sz=$(wc -c < "${OUTPUT_DIR}/${name}.pdf")
    echo "✅ ($(( sz / 1024 ))KB)"
  else
    echo "❌ (not PDF)"
    rm -f "${OUTPUT_DIR}/${name}.pdf"
  fi
done < "$1"
```

## Input file format (urls.txt)

```
Author_Year_short-title|https://journals.plos.org/plosone/article/file?id=DOI&type=printable
Author_Year_short-title|https://bmccancer.biomedcentral.com/counter/pdf/DOI.pdf
```
