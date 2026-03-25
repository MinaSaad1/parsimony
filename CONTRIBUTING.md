# Contributing to Parsimony

Thanks for your interest in contributing!

## Getting Started

```bash
git clone https://github.com/MinaSaad1/parsimony.git
cd parsimony
pip install -e ".[dev]"
```

## Development Workflow

1. Create a branch from `main`
2. Write tests first, then implement
3. Run the checks:

```bash
pytest                # tests + coverage (must be 80%+)
ruff check src/       # lint
mypy src/             # type check
```

4. Open a PR against `main`

## Code Style

- Python 3.11+ with type hints everywhere
- Immutable dataclasses (frozen=True)
- Decimal precision for all cost calculations
- Max line length: 100 characters
- Follow existing patterns in the codebase

## Reporting Bugs

Open an issue with:
- What you expected
- What happened instead
- `parsimony --version` output
- Python version

## Feature Requests

Open an issue describing the use case. We value simplicity, so features should solve a real problem for Claude Code users.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
