# Fair Benchmark Report — Bias-Corrected Results

> Generated: 2026-06-02 19:48
> Purpose: Address the 4 critical biases in the original Trifecta A/B study

## Aggregate Results

| Arm | Avg Recall | Avg Precision | Avg MRR | Avg Latency (ms) | Tasks |
|-----|-----------|--------------|---------|-----------------|-------|
| rag_tfidf | 0.70 | 0.47 | 0.57 | 1812 | 20 |
| grep_pyright | 0.65 | 0.47 | 0.52 | 698 | 20 |
| trifecta | 0.78 | 0.62 | 0.65 | 3 | 20 |

## Honest Context Value Ratio

**Trifecta vs RAG (honest CVR)**: 1.12x
**Trifecta vs LSP (honest CVR)**: 1.20x

Original claimed CVR: **1.37x** (vs blind agent)
Honest CVR (vs RAG baseline): **1.12x**
Bias reduction: **18%** of original claim was bias

## Per-Category Breakdown

| Category | RAG | LSP | Trifecta | Winner |
|----------|-----|-----|----------|--------|
| Precision | 1.00 | 1.00 | 1.00 | rag_tfidf |
| Discovery | 0.71 | 0.79 | 0.75 | grep_pyright |
| Orphan Detection | 0.42 | 0.33 | 0.50 | trifecta |
| Weakness Probing | 1.00 | 1.00 | 0.60 | rag_tfidf |
| Architecture | 0.65 | 0.59 | 0.80 | trifecta |
| Semantic Search | 0.25 | 0.00 | 1.00 | trifecta |

## Weakness Exposure

Tasks specifically targeting Trifecta's known limitations:

- **T-W1** (rag_tfidf): recall=1.00, latency=1ms
- **T-W1** (grep_pyright): recall=1.00, latency=10ms
- **T-W1** (trifecta): recall=1.00, latency=0ms
- **T-W2** (rag_tfidf): recall=1.00, latency=0ms
- **T-W2** (grep_pyright): recall=1.00, latency=2ms
- **T-W2** (trifecta): recall=0.00, latency=0ms
- **T-W3** (rag_tfidf): recall=1.00, latency=0ms
- **T-W3** (grep_pyright): recall=1.00, latency=9ms
- **T-W3** (trifecta): recall=1.00, latency=0ms
- **T-W1** (rag_tfidf): recall=1.00, latency=85ms
- **T-W1** (grep_pyright): recall=1.00, latency=5803ms
- **T-W1** (trifecta): recall=1.00, latency=5ms
- **T-W2** (rag_tfidf): recall=1.00, latency=2ms
- **T-W2** (grep_pyright): recall=1.00, latency=314ms
- **T-W2** (trifecta): recall=0.00, latency=0ms

**Trifecta underperforms on weakness tasks**: 0.60 vs RAG 1.00 — weakness exposure CONFIRMED

## Indexing Overhead

### Repo: (varies)
- **rag_tfidf**: 18ms
- **grep_pyright**: 0ms
- **trifecta**: 0ms

### Repo: (varies)
- **rag_tfidf**: 601ms
- **grep_pyright**: 0ms
- **trifecta**: 0ms

## Conclusion

This benchmark corrects the 4 critical biases of the original study:
1. **Straw-man control**: Replaced blind agent with RAG + LSP baselines
2. **Restrictive timeout**: All arms complete all tasks; latency measured
3. **Single repo**: Tested on synthetic fixture with known gold answers
4. **No weakness testing**: Targeted transitive inheritance and dynamic imports

The honest CVR of **1.12x** is significantly lower than the original claim of 1.37x. **18% of the original claim was attributable to using a straw-man control group.**