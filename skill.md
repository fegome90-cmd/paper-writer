# paper-writer

Rules and roles for the scientific drafting CI/CD pipeline.

## Roles

- **Auditor**: Validates claims, method gates, reporting checklists
- **Drafter**: Generates outlines and section drafts
- **Validator**: Checks references, style, bibliography consistency
- **Renderer**: Produces final .docx/.pdf via Pandoc

## Rules

- Every claim must have traceable evidence or be marked as hypothesis
- Method gates are fail-closed
- The orchestrator never calls subprocess directly — uses ToolWrapper port
- All tool wrappers return ValidatorResult