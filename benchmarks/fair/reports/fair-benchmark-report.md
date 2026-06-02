# Fair Benchmark Report — Bias-Corrected Results

> Generated: 2026-06-02 17:12
> Purpose: Address the 4 critical biases in the original Trifecta A/B study

## Aggregate Results

| Arm | Avg Recall | Avg Precision | Avg MRR | Avg Latency (ms) | Tasks |
|-----|-----------|--------------|---------|-----------------|-------|
| rag_tfidf | 0.66 | 0.37 | 0.48 | 80 | 20 |
| grep_pyright | 0.59 | 0.37 | 0.44 | 714 | 20 |
| trifecta | 0.63 | 0.38 | 0.49 | 4 | 20 |

## Honest Context Value Ratio

**Trifecta vs RAG (honest CVR)**: 0.96x
**Trifecta vs LSP (honest CVR)**: 1.06x

Original claimed CVR: **1.37x** (vs blind agent)
Honest CVR (vs RAG baseline): **0.96x**
Bias reduction: **30%** of original claim was bias

## Per-Category Breakdown

| Category | RAG | LSP | Trifecta | Winner |
|----------|-----|-----|----------|--------|
| Precision | 1.00 | 1.00 | 1.00 | rag_tfidf |
| Discovery | 0.71 | 0.67 | 0.75 | trifecta |
| Orphan Detection | 0.50 | 0.50 | 1.00 | trifecta |
| Weakness Probing | 0.80 | 0.80 | 0.60 | rag_tfidf |
| Architecture | 0.65 | 0.59 | 0.30 | rag_tfidf |
| Semantic Search | 0.25 | 0.00 | 0.25 | rag_tfidf |

## Weakness Exposure

Tasks specifically targeting Trifecta's known limitations:

- **T-W1** (rag_tfidf): recall=1.00, latency=0ms
- **T-W1** (grep_pyright): recall=1.00, latency=6ms
- **T-W1** (trifecta): recall=1.00, latency=0ms
- **T-W2** (rag_tfidf): recall=0.00, latency=0ms
- **T-W2** (grep_pyright): recall=0.00, latency=1ms
- **T-W2** (trifecta): recall=0.00, latency=0ms
- **T-W3** (rag_tfidf): recall=1.00, latency=0ms
- **T-W3** (grep_pyright): recall=1.00, latency=6ms
- **T-W3** (trifecta): recall=1.00, latency=0ms
- **T-W1** (rag_tfidf): recall=1.00, latency=71ms
- **T-W1** (grep_pyright): recall=1.00, latency=4430ms
- **T-W1** (trifecta): recall=1.00, latency=4ms
- **T-W2** (rag_tfidf): recall=1.00, latency=1ms
- **T-W2** (grep_pyright): recall=1.00, latency=429ms
- **T-W2** (trifecta): recall=0.00, latency=0ms

**Trifecta underperforms on weakness tasks**: 0.60 vs RAG 0.80 — weakness exposure CONFIRMED

## Indexing Overhead

### Repo: (varies)
- **rag_tfidf**: 27ms
- **grep_pyright**: 0ms
- **trifecta**: 0ms

### Repo: (varies)
- **rag_tfidf**: 426ms
- **grep_pyright**: 0ms
- **trifecta**: 0ms

## Conclusion

This benchmark corrects the 4 critical biases of the original study:
1. **Straw-man control**: Replaced blind agent with RAG + LSP baselines
2. **Restrictive timeout**: All arms complete all tasks; latency measured
3. **Single repo**: Tested on synthetic fixture with known gold answers
4. **No weakness testing**: Targeted transitive inheritance and dynamic imports

The honest CVR of **0.96x** is significantly lower than the original claim of 1.37x. **30% of the original claim was attributable to using a straw-man control group.**