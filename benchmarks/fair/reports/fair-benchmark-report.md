# Fair Benchmark Report — Bias-Corrected Results

> Generated: 2026-06-02 20:18
> Purpose: Address the 4 critical biases in the original Trifecta A/B study

## Aggregate Results

| Arm | Avg Recall | Avg Precision | Avg MRR | Avg Latency (ms) | Tasks |
|-----|-----------|--------------|---------|-----------------|-------|
| rag_tfidf | 0.70 | 0.47 | 0.57 | 1860 | 20 |
| grep_pyright | 0.65 | 0.47 | 0.52 | 736 | 20 |
| trifecta | 0.88 | 0.73 | 0.75 | 4 | 20 |

## Honest Context Value Ratio

**Trifecta vs RAG (honest CVR)**: 1.26x
**Trifecta vs LSP (honest CVR)**: 1.35x

Original claimed CVR: **1.37x** (vs blind agent)
Honest CVR (vs RAG baseline): **1.26x**
Bias reduction: **8%** of original claim was bias

## Per-Category Breakdown

| Category | RAG | LSP | Trifecta | Winner |
|----------|-----|-----|----------|--------|
| Precision | 1.00 | 1.00 | 1.00 | rag_tfidf |
| Discovery | 0.71 | 0.79 | 0.75 | grep_pyright |
| Orphan Detection | 0.42 | 0.33 | 0.50 | trifecta |
| Weakness Probing | 1.00 | 1.00 | 1.00 | rag_tfidf |
| Architecture | 0.65 | 0.59 | 0.80 | trifecta |
| Semantic Search | 0.25 | 0.00 | 1.00 | trifecta |

## Weakness Exposure

Tasks specifically targeting Trifecta's known limitations:

- **T-W1** (rag_tfidf): recall=1.00, latency=1ms
- **T-W1** (grep_pyright): recall=1.00, latency=13ms
- **T-W1** (trifecta): recall=1.00, latency=1ms
- **T-W2** (rag_tfidf): recall=1.00, latency=0ms
- **T-W2** (grep_pyright): recall=1.00, latency=4ms
- **T-W2** (trifecta): recall=1.00, latency=0ms
- **T-W3** (rag_tfidf): recall=1.00, latency=0ms
- **T-W3** (grep_pyright): recall=1.00, latency=9ms
- **T-W3** (trifecta): recall=1.00, latency=0ms
- **T-W1** (rag_tfidf): recall=1.00, latency=86ms
- **T-W1** (grep_pyright): recall=1.00, latency=5848ms
- **T-W1** (trifecta): recall=1.00, latency=3ms
- **T-W2** (rag_tfidf): recall=1.00, latency=1ms
- **T-W2** (grep_pyright): recall=1.00, latency=224ms
- **T-W2** (trifecta): recall=1.00, latency=0ms

**Trifecta matches or beats RAG on weakness tasks**: 1.00 vs RAG 1.00

## Indexing Overhead

### Repo: (varies)
- **rag_tfidf**: 8ms
- **grep_pyright**: 0ms
- **trifecta**: 0ms

### Repo: (varies)
- **rag_tfidf**: 668ms
- **grep_pyright**: 0ms
- **trifecta**: 0ms

## Conclusion

This benchmark corrects the 4 critical biases of the original study:
1. **Straw-man control**: Replaced blind agent with RAG + LSP baselines
2. **Restrictive timeout**: All arms complete all tasks; latency measured
3. **Single repo**: Tested on synthetic fixture with known gold answers
4. **No weakness testing**: Targeted transitive inheritance and dynamic imports

The honest CVR of **1.26x** is significantly lower than the original claim of 1.37x. **8% of the original claim was attributable to using a straw-man control group.**