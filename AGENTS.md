# AGENTS.md

Repository guide for agentic coding assistants working in `muffin-redis`.

## Project Snapshot

- Package: `muffin-redis`
- Python: `>=3.11,<4`
- Build backend: `uv_build`
- Main implementation: `muffin_redis/__init__.py`
- Tests: `tests.py`
- Core tools: `uv`, `pytest`, `ruff`, `pyrefly`, `pre-commit`

## Environment Setup

Use `uv` for all local workflows.

```bash
uv sync --all-extras --dev
```

For CI parity, use locked deps:

```bash
uv sync --locked --all-extras --dev
```

## Build / Lint / Test Commands

Preferred direct commands:

```bash
# Full tests
uv run pytest
# Single test function
uv run pytest tests.py::test_muffin_redis
# Single test by keyword
uv run pytest -k pubsub
# Type check
uv run pyrefly check
# Lint / format
uv run ruff check
uv run ruff format
# Run all hooks
uv run pre-commit run --all-files
# Build artifacts
uv build
```

Make targets:

```bash
make test      # same as make t
make lint      # runs make types + ruff check
make types     # runs pyrefly check
make clean

# Release helpers
make patch     # bump patch version and run release flow
make minor     # bump minor version and run release flow
make major     # bump major version and run release flow
```

Important notes:

- `make test` runs the full suite only.
- For one test, use `uv run pytest tests.py::test_name`.
- Pytest default options come from `pyproject.toml`: `-lxsv tests.py`.

## CI Expectations

CI workflow: `.github/workflows/tests.yml`.
Pipeline commands:

1. `uv sync --locked --all-extras --dev`
2. `uv run pyrefly check`
3. `uv run ruff check`
4. `uv run pytest`

Compatibility target: Python `3.11`, `3.12`, `3.13`, `3.14`.

## Code Style Guidelines

### Formatting and linting

- Ruff is authoritative for formatting and linting.
- Config lives in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`.
- Line length: `100`; target version: `py311`.
- Lint set is strict (`select = ["ALL"]`) with explicit ignore list.
- After edits, run `uv run ruff format` then `uv run ruff check`.

### Imports

- Keep imports at module top by default.
- Group order: standard library, third-party, local package imports.
- Separate import groups with a single blank line.
- Use `TYPE_CHECKING` for typing-only imports.
- Use local inline imports only when useful for optional dependency behavior
  (example: lazy `fakeredis` import in plugin setup).

### Typing

- Add type hints for public APIs and non-trivial internals.
- Prefer modern syntax: `A | B`, built-in collections (`list[str]`, etc.).
- Use `ClassVar` for class-level config constants.
- Prefer explicit, narrow types over `Any`.
- Keep `pyrefly` passing before finalizing.

### Naming conventions

- Modules/files: `snake_case`.
- Functions/methods/variables: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Muffin plugin convention:
  - class attribute `name` for plugin key
  - class attribute `defaults` for default config

### Async and concurrency

- This library is async-first (`redis.asyncio`, async lifecycle hooks).
- Avoid blocking calls inside async functions.
- Use `async with` for lifecycle-bound resources.
- Prefer explicit awaits and predictable concurrency in tests.

### Error handling

- Prefer guard clauses and early exits over deep nesting.
- Raise clear built-in exceptions for invalid states.
- Catch only specific exceptions you can recover from.
- Use `contextlib.suppress(...)` only for narrow, intentional fallbacks.
- Do not silently swallow unexpected errors.

### Control flow and design

- Keep functions focused and single-purpose.
- Keep side effects explicit and local.
- Preserve existing `Plugin` behavior unless task requires change.

### Comments and docstrings

- Follow existing concise docstring style.
- Add comments only when behavior is not obvious from code.
- Avoid comments that restate what the code already says.

## Testing Guidelines

- Test framework: `pytest` with async tests in `tests.py`.
- Prefer focused tests close to related behavior (currently in `tests.py`).
- For bug fixes, add/update a regression test where practical.

Single-test examples:

```bash
uv run pytest tests.py::test_pool
uv run pytest tests.py::test_muffin_redis_pubsub
uv run pytest -k jsonnify
```

## Commit and Hook Conventions

- Install hooks with `uv run pre-commit install`.
- Conventional commits are enforced via `.pre-commit-config.yaml` and `.git-commits.yaml`.
- Allowed types: `build`, `chore`, `docs`, `feat`, `fix`, `merge`, `ops`, `perf`, `refactor`,
  `style`, `test`.

## Changelog

- Maintain `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
- For every user-visible change (features, fixes, refactors, breaking changes), add an entry
  under `[Unreleased]` in the appropriate section (`Added`, `Changed`, `Fixed`, `Removed`).
- When a release is cut, move the `[Unreleased]` entries under a new version heading.

## Release Process

- Release automation is defined in `Makefile` (`make release`, `make patch`, `make minor`,
  `make major`).
- `make patch|minor|major` calls `make release VERSION=<part>`.
- The flow checks out and pulls `main` and `develop`, bumps version with
  `uv version --bump`, updates `uv.lock`, creates a `build(release): <version>` commit,
  and creates a git tag.
- It then merges `develop -> main`, then `main -> develop`, and pushes branches and tags.
- Use release commands only when you intentionally want branch switching, merge commits,
  tagging, and remote pushes.

Before finalizing, run:

```bash
uv run ruff format
uv run ruff check
uv run pyrefly check
uv run pytest
```

## Agent Execution Checklist

1. Sync dependencies with `uv`.
2. Make minimal, targeted changes.
3. Update `CHANGELOG.md` under `[Unreleased]` for user-visible changes.
4. Run format + lint + type checks.
5. Run relevant tests (single during iteration, full before finish).
6. Keep commit messages conventional.
