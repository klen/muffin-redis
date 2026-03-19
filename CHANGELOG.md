# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
