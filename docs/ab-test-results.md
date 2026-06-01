# Trifecta Context Injection — A/B Test Suite

> Purpose: Measure the impact of Trifecta context injection on code analysis tasks.
> Results feed directly into a white paper on AI agent context augmentation.

## Methodology

### Setup
- **Agent A (control)**: `TRIFECTA_DISABLE=1` — no Trifecta context injected
- **Agent B (treatment)**: Extension active — graph symbols + context chunks injected via `before_agent_start`
- **Model**: `zai/glm-5-turbo` (same for both)
- **Runtime**: `pi --mode json -nc -p @prompt.txt`
- **Project**: `/Users/felipe_gonzalez/Developer/agent_h/trifecta_dope`
- **Graph state**: 264 nodes, 219 edges, stale (10 days old)

### Controls
- Same model, same prompt, same project directory
- Both agents launched from the same bash script in parallel
- Both agents use `-nc` flag (no context files)
- Both agents write output to a deterministic file path
- Scoring is automated against ground truth verified from source code

### Test Categories

| # | Category | What it tests | Expected Trifecta advantage |
|---|----------|---------------|----------------------------|
| T1 | Precision | Exact line numbers, function signatures | HIGH — graph provides exact symbol locations |
| T2 | Discovery | Find specific callers/callees chains | HIGH — graph enables relational queries |
| T3 | Architecture | Understand component connections | MEDIUM — graph shows edges, but model can read files |
| T4 | Debugging | Diagnose a failure scenario | MEDIUM — context helps narrow search space |
| T5 | Hard/Unfamiliar | Analyze code the model has never seen | HIGH — context provides the only map of the codebase |
| T6 | Concise Query | Answer with minimal file reads | HIGH — context reduces exploration rounds |

### Scoring Rubric

| Dimension | Score | Criteria |
|-----------|-------|----------|
| **Completeness** | 0-5 | How many of the requested items were found |
| **Accuracy** | 0-5 | Are the claims correct (file paths, line numbers, behavior) |
| **Precision** | 0-5 | Are line references exact or approximate |
| **Efficiency** | 0-5 | Words used / file reads needed (less = better) |
| **Confidence** | reported | Agent's self-reported confidence |

### Metric: Context Value Ratio

```
context_value_ratio = score_B / score_A
```

- `> 1.0`: Trifecta context helps
- `= 1.0`: No difference
- `< 1.0`: Trifecta context hurts (noise/confusion)

---

## Results

### Test T1: Precision (Architecture Analysis)

**Task**: Answer 5 questions about the Oracle system with exact file paths and line numbers.

**Status**: ✅ Completed

| Metric | Agent A (control) | Agent B (w/ context) |
|--------|-------------------|----------------------|
| Files referenced | 7 | 7 |
| Answer length (words) | 1272 | 971 |
| Signal types found | 15/15 | 15/15 |
| Line refs verified | off by 1-2 | 4/4 exact |
| graph_service.py refs | 9 | 13 |
| Wall time | ~75s | ~75s |

**Score**: A=3.5/5, B=4.5/5 → **context_value_ratio = 1.29x**

**Key finding**: Trifecta context improved LINE NUMBER PRECISION. Both found the same files and signals, but B's references were pin-point accurate while A was off by 1-2 lines.

### Test T2: Discovery

**Status**: 🔄 Pending

### Test T3: Architecture

**Status**: 🔄 Pending

### Test T4: Debugging

**Status**: 🔄 Pending

### Test T5: Hard/Unfamiliar

**Status**: 🔄 Pending

### Test T6: Concise Query

**Status**: 🔄 Pending

---

## Aggregate Analysis

*(Filled after all tests complete)*

---

## Appendix A: Raw Output Paths

| Test | Agent A | Agent B |
|------|---------|---------|
| T1 | `/tmp/ab-test-agent-a.md` (10535 bytes) | `/tmp/ab-test-agent-b.md` (8591 bytes) |
| T2 | `/tmp/ab-t2-agent-a.md` | `/tmp/ab-t2-agent-b.md` |
| T3 | `/tmp/ab-t3-agent-a.md` | `/tmp/ab-t3-agent-b.md` |
| T4 | `/tmp/ab-t4-agent-a.md` | `/tmp/ab-t4-agent-b.md` |
| T5 | `/tmp/ab-t5-agent-a.md` | `/tmp/ab-t5-agent-b.md` |
| T6 | `/tmp/ab-t6-agent-a.md` | `/tmp/ab-t6-agent-b.md` |

## Appendix B: Extension Configuration

```typescript
// 02-trifecta-context-loader.ts — A/B gate
pi.on("before_agent_start", async (event) => {
    if (process.env.TRIFECTA_DISABLE) {
        console.debug("[trifecta-context-loader] TRIFECTA_DISABLE set, skipping injection");
        return;
    }
    // ... normal injection logic
});
```

## Appendix C: Reproduction

```bash
# Run a single A/B test
cd /Users/felipe_gonzalez/Developer/agent_h/trifecta_dope

# Agent A (control)
TRIFECTA_DISABLE=1 pi --provider zai --model glm-5-turbo --mode json -nc -p @/tmp/ab-t2-prompt-control.txt

# Agent B (treatment)
pi --provider zai --model glm-5-turbo --mode json -nc -p @/tmp/ab-t2-prompt-treatment.txt
```
