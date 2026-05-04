# Agent Instructions

## Prime Directive

Do not proceed with work when there are unanswered questions.

If you have questions, stop as soon as you have them and ask before proceeding. Do not guess, do not fill in missing requirements silently, and do not continue implementation while a decision is unclear.

## Project Workflow

This is a Python package managed with `uv`.

- Use `uv` to manage the package environment.
- Use `uv add` to add runtime dependencies.
- Use `uv add --dev` to add development dependencies.
- Do not edit `pyproject.toml` directly to add or remove dependencies.
- Run project commands through `uv run`.

Examples:

```bash
uv add bleak
uv add --dev pytest ruff pre-commit ty
uv run pytest
uv run ruff check .
uv run ty check
```

## Testing

Use test-driven development.

- Write or update tests before implementing behavior.
- Use `pytest` as the test framework.
- Run tests with `uv run pytest`.
- Keep tests focused on behavior.
- Use fixtures where they make setup clearer and reduce duplication.
- Organize tests so protocol logic, BLE client behavior, capture parsing, and CLI behavior can be tested separately.
- Hardware-dependent tests must be opt-in and must not run during the default test suite.

## Linting And Type Checking

Use:

- `ruff` for linting.
- `pre-commit` via `prek`/`pre-commit` workflow as configured for the project.
- `ty` for type checking.

Run checks through `uv run`, for example:

```bash
uv run ruff check .
uv run ty check
uv run pytest
```

## Dependency Policy

- Add dependencies only when they are needed for the current task.
- Prefer small, well-maintained dependencies.
- Keep Bluetooth runtime dependencies minimal; `bleak` is the expected BLE client library.
- Keep reverse-engineering tooling dependencies as development dependencies unless they are required by the shipped package.

## Implementation Style

- Keep protocol encoding pure and testable without hardware.
- Keep live Bluetooth code behind narrow interfaces that can be mocked in tests.
- Preserve raw-research commands separately from stable high-level SDK commands.
- Validate user inputs before sending Bluetooth writes.
- Do not send guessed control packets as part of high-level behavior.
