# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Python 3.15 support (classifier, CI matrix, tox environments).
- README section documenting the public API: `client`, `set`, `get`, `lock` and attribute proxying.
- `tox` environments `py311`-`py315` and `pypy311`.

### Changed
- `get()` no longer accepts `**options`: `redis-py`'s `GET` takes only the key, so any option raised
  `TypeError`.
- Dev tooling aligned with the `muffin-rest` reference (dependency group, ruff ignore list,
  pre-commit hook versions, Makefile targets).
- README references `redis.asyncio` instead of the archived `aioredis` project.
- Tests are pinned to asyncio: `redis.asyncio` does not work under trio/curio.

### Fixed
- `fake: true` lock no longer deletes a key that had already expired and been taken by another
  worker (it used to release a lock it no longer owned).
- `startup`/`shutdown` no longer write the Redis password into the log when credentials come from
  the URL.
- `Plugin.__getattr__` now raises `AttributeError` for missing or dunder attributes instead of
  `RecursionError`/`RuntimeError`, so `getattr(plugin, name, default)`, `hasattr()` and `copy.copy()`
  work as expected.
- A disabled plugin no longer builds a Redis client, and `setup()` returns `False` for it.
- `db` is honoured in `fake: true` mode instead of silently using database 0.
- README documented a non-existent `address` option, the wrong extra name (`fakeredis` instead of
  `fake`), `expire=` instead of the supported `ex=` argument and the wrong `poolsize=0` semantics.
- `make clean` removed `__pycache__` from an undefined `$(MODULE)` directory.

## [4.0.0] - 2026-06-26

### Added
- Fake lock support via `SET NX` + `DEL` (no Lua dependency) for `fake: true` mode.

### Changed
- Replaced `redislite` with `fakeredis` for testing without a real Redis server.
- Split plugin code into `plugin.py` (main plugin) and `fake.py` (FakeRedis helpers).
- Raised minimum Python version from 3.10 to 3.11.

### Removed
- `redislite` config option and dependency. Use `fake: true` with `fakeredis` instead.
- Python 3.10 support.

## [3.11.0] - 2026-03-19

### Added
- Added an async context-manager lock API: `Plugin.lock(...)` yields an acquisition flag and
  releases automatically on context exit.
- Added lock-context coverage in `tests.py` for non-blocking nested acquisition behavior.
- Added `AGENTS.md` with repository-specific guidance for coding agents.
- Documented build/lint/test workflows, single-test `pytest` commands, style conventions,
  and release instructions for agents.

## [3.10.0] - 2026-03-19

### Build
- Release `3.10.0`.
