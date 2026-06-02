# Fair Benchmark Report — Bias-Corrected Results

> Generated: 2026-06-02 16:55
> Purpose: Address the 4 critical biases in the original Trifecta A/B study

## Aggregate Results

| Arm | Avg Recall | Avg Precision | Avg MRR | Avg Latency (ms) | Tasks |
|-----|-----------|--------------|---------|-----------------|-------|
| rag_tfidf | 0.74 | 0.44 | 0.54 | 19 | 16 |
| grep_pyright | 0.64 | 0.45 | 0.47 | 2165 | 16 |
| trifecta | 0.60 | 0.40 | 0.43 | 0 | 16 |

## Honest Context Value Ratio

**Trifecta vs RAG (honest CVR)**: 0.81x
**Trifecta vs LSP (honest CVR)**: 0.94x

Original claimed CVR: **1.37x** (vs blind agent)
Honest CVR (vs RAG baseline): **0.81x**
Bias reduction: **41%** of original claim was bias

## Per-Category Breakdown

| Category | RAG | LSP | Trifecta | Winner |
|----------|-----|-----|----------|--------|
| Precision | 1.00 | 1.00 | 1.00 | rag_tfidf |
| Discovery | 0.83 | 0.67 | 0.67 | rag_tfidf |
| Orphan Detection | 0.50 | 0.50 | 0.50 | rag_tfidf |
| Weakness Probing | 0.75 | 0.75 | 0.75 | rag_tfidf |
| Architecture | 0.65 | 0.59 | 0.30 | rag_tfidf |
| Semantic Search | 0.50 | 0.00 | 0.00 | rag_tfidf |

## Weakness Exposure

Tasks specifically targeting Trifecta's known limitations:

- **T-W1** (rag_tfidf): recall=1.00, latency=0ms
- **T-W1** (grep_pyright): recall=1.00, latency=1ms
- **T-W1** (trifecta): recall=1.00, latency=0ms
- **T-W2** (rag_tfidf): recall=0.00, latency=0ms
- **T-W2** (grep_pyright): recall=0.00, latency=0ms
- **T-W2** (trifecta): recall=0.00, latency=0ms
- **T-W3** (rag_tfidf): recall=1.00, latency=0ms
- **T-W3** (grep_pyright): recall=1.00, latency=1ms
- **T-W3** (trifecta): recall=1.00, latency=0ms
- **T-W1** (rag_tfidf): recall=1.00, latency=14ms
- **T-W1** (grep_pyright): recall=1.00, latency=795ms
- **T-W1** (trifecta): recall=1.00, latency=0ms

**Trifecta matches or beats RAG on weakness tasks**: 0.75 vs RAG 0.75

## Indexing Overhead

### Repo: (varies)
- **rag_tfidf**: 1ms
- **grep_pyright**: 0ms
- **trifecta**: 0ms

### Repo: (varies)
- **rag_tfidf**: 95ms
- **grep_pyright**: 0ms
- **trifecta**: 0ms

## Conclusion

This benchmark corrects the 4 critical biases of the original study:
1. **Straw-man control**: Replaced blind agent with RAG + LSP baselines
2. **Restrictive timeout**: All arms complete all tasks; latency measured
3. **Single repo**: Tested on synthetic fixture with known gold answers
4. **No weakness testing**: Targeted transitive inheritance and dynamic imports

The honest CVR of **0.81x** is significantly lower than the original claim of 1.37x. **41% of the original claim was attributable to using a straw-man control group.**