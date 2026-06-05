# Warrants — Toulmin Model Reference

Use this guide to make the logical bridge between evidence and claims explicit.

## Toulmin Components

| Component | Role |
|-----------|------|
| **Claim** | The assertion the essay defends |
| **Evidence** | Data, studies, or observations supporting the claim |
| **Warrant** | The logical principle connecting evidence to claim |
| **Backing** | Additional support for the warrant itself |
| **Qualifier** | Scope limitation ("usually", "in most cases") |
| **Rebuttal** | Conditions under which the claim would not hold |

## Why Warrants Matter

A claim + evidence without a warrant is a non sequitur. The reader must infer
the reasoning — and may infer wrong. Explicit warrants close that gap.

## Good vs. Missing Warrants

**Missing warrant:**
> "Smith (2023) found a 40% reduction in error rates. Therefore, the policy
> should be adopted nationwide." *(How does one study generalize to nationwide
> policy? The warrant is assumed, not stated.)*

**Explicit warrant:**
> "Smith (2023) found a 40% reduction in error rates under controlled
> conditions. Because the study's sample demographics match the national
> population profile, the results are likely to scale. Therefore, the policy
> should be adopted nationwide." *(Warrant: representative samples support
> generalization.)*

## Warrants in the Evidence Passport

The `claim_links` object connects claims to evidence. Each link should include
a `warrant` field that states the reasoning principle. If the warrant field is
empty or vague, the link fails the integrity gate.

## Decision Gate

| If | Then |
|----|------|
| Claim-evidence pair has no warrant | Flag as unsupported inference |
| Warrant is circular ("it's true because it's true") | Rewrite with external logic |
| Warrant relies on unstated assumption | Make the assumption explicit or add backing |
| Warrant contradicts another warrant in the same essay | Flag for resolution |
