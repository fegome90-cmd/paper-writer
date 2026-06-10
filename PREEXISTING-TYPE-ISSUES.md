# Pre-existing Issues

Type-check and technical debt items discovered during autoresearch but NOT introduced by current changes.

## mypy errors

### PE-1: QualityAppraisalValidator.validate() type mismatch
- **File**: `cli/paper/commands/audit.py:389`
- **Error**: `Argument 1 to "validate" of "QualityAppraisalValidator" has incompatible type "Any | list[Any]"; expected "Path"`
- **Root cause**: `audit.py` calls `validator.validate(papers)` passing parsed JSON list, but the method signature expects `validate(self, evidence_path: Path, ...)`. The method internally reads the file — caller shouldn't pre-parse.
- **Severity**: mypy error, not a runtime bug (callers always provide valid paths at runtime)
- **Fix**: Either change the CLI to pass the path directly, or update the validator's signature to accept `Path | list[dict]`.

### PE-2: Missing type annotation in test mock
- **File**: `tests/cli/test_paper_cli.py:505`
- **Error**: `Function is missing a type annotation`
- **Code**: `def mock_build(*args, **kwargs):`
- **Severity**: mypy warning, test-only code
- **Fix**: Add `def mock_build(*args: Any, **kwargs: Any) -> Any:` or `-> None:`.

## Architecture notes

### PE-3: PREEXISTING-ISSUES.md already exists
- Previous autoresearch sessions documented 5 TODOs in `PREEXISTING-ISSUES.md` from run #493.
- These are separate from the issues above.
