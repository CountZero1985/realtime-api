# Linting and Code Quality

## Tools

- **Linter/Formatter**: [ruff](https://docs.astral.sh/ruff/)
- **Type Checker**: mypy (optional, not configured in pyproject.toml yet)

## Configuration

No explicit ruff configuration exists in `pyproject.toml` — ruff uses defaults:
- Target Python: 3.12+ (inferred from `requires-python = ">=3.12"`)
- Default rule set: Pyflakes (`F`) + pycodestyle errors (`E`)
- Line length: 88 (ruff default)

## Running Checks

```bash
# Lint the package
ruff check openai_apis/

# Lint with auto-fix
ruff check openai_apis/ --fix

# Format the package
ruff format openai_apis/

# Check formatting (dry-run)
ruff format openai_apis/ --check

# Lint examples too
ruff check examples/

# Lint everything
ruff check .
```

## Coverage Configuration

Coverage is configured in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["openai_apis"]
omit = ["*/tests/*", "*/examples/*"]
```

Coverage runs automatically with pytest via `addopts = "--strict-markers --cov=openai_apis --cov-report=term-missing"`.

## Adding ruff Rules

To extend rules, add to `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]  # Add isort (I) and pyupgrade (UP)
```
