# Fair Benchmark Report — Bias-Corrected Results

> Generated: 2026-06-02 16:46
> Purpose: Address the 4 critical biases in the original Trifecta A/B study

## Aggregate Results

| Arm | Avg Recall | Avg Precision | Avg MRR | Avg Latency (ms) | Tasks |
|-----|-----------|--------------|---------|-----------------|-------|
| rag_tfidf | 0.75 | 0.70 | 0.24 | 18 | 16 |
| lsp_pyright | 0.88 | 0.74 | 0.49 | 2042 | 16 |
| trifecta | 0.44 | 0.44 | 0.04 | 0 | 16 |

## Honest Context Value Ratio

**Trifecta vs RAG (honest CVR)**: 0.58x
**Trifecta vs LSP (honest CVR)**: 0.50x

Original claimed CVR: **1.37x** (vs blind agent)
Honest CVR (vs RAG baseline): **0.58x**
Bias reduction: **57%** of original claim was bias

## Per-Category Breakdown

| Category | RAG | LSP | Trifecta | Winner |
|----------|-----|-----|----------|--------|
| Precision | 0.67 | 0.67 | 0.67 | rag_tfidf |
| Discovery | 0.67 | 1.00 | 0.33 | lsp_pyright |
| Orphan Detection | 1.00 | 1.00 | 1.00 | rag_tfidf |
| Weakness Probing | 0.75 | 1.00 | 0.50 | lsp_pyright |
| Architecture | 1.00 | 0.50 | 0.00 | rag_tfidf |
| Semantic Search | 0.50 | 1.00 | 0.00 | lsp_pyright |

## Weakness Exposure

Tasks specifically targeting Trifecta's known limitations:

- **T-W1** (rag_tfidf): recall=1.00, latency=0ms
- **T-W1** (lsp_pyright): recall=1.00, latency=1ms
- **T-W1** (trifecta): recall=1.00, latency=0ms
- **T-W2** (rag_tfidf): recall=1.00, latency=0ms
- **T-W2** (lsp_pyright): recall=1.00, latency=0ms
- **T-W2** (trifecta): recall=0.00, latency=0ms
- **T-W3** (rag_tfidf): recall=1.00, latency=0ms
- **T-W3** (lsp_pyright): recall=1.00, latency=1ms
- **T-W3** (trifecta): recall=1.00, latency=0ms
- **T-W1** (rag_tfidf): recall=0.00, latency=0ms
- **T-W1** (lsp_pyright): recall=1.00, latency=140ms
- **T-W1** (trifecta): recall=0.00, latency=0ms

**Trifecta underperforms on weakness tasks**: 0.50 vs RAG 0.75 — weakness exposure CONFIRMED

## Indexing Overhead

### Repo: (varies)
- **rag_tfidf**: 1ms
- **lsp_pyright**: 0ms
- **trifecta**: 0ms

### Repo: (varies)
- **rag_tfidf**: 92ms
- **lsp_pyright**: 0ms
- **trifecta**: 0ms

## Conclusion

This benchmark corrects the 4 critical biases of the original study:
1. **Straw-man control**: Replaced blind agent with RAG + LSP baselines
2. **Restrictive timeout**: All arms complete all tasks; latency measured
3. **Single repo**: Tested on synthetic fixture with known gold answers
4. **No weakness testing**: Targeted transitive inheritance and dynamic imports

The honest CVR of **0.58x** is significantly lower than the original claim of 1.37x. **57% of the original claim was attributable to using a straw-man control group.**