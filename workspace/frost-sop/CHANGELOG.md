# Changelog

All notable changes to FROST-SOP are documented in this file.

## [v5.0.0] - 2026-07-02

### P0 Fixes
- **DB singleton isolation**: `threading.Lock` serializes write operations + `PRAGMA busy_timeout=5000` (core/db.py)
- **SSE endpoint fix**: `/api/logs` removed from parametrized GET tests (SSE needs integration test)
- **TOCTOU race condition**: `_assemble_child` protected with `try/except IntegrityError` (skills/orchestration.py)
- **Event bus retry**: `_persist_event` retry backoff reduced 50ms -> 1ms (core/event_bus.py)
- **Test isolation**: autouse fixture in conftest.py resets all singletons per test

### Coverage Tests (+247)
- `test_armory_coverage.py`: 107 tests -> armory.py 98.89%
- `test_elder_coverage.py`: 66 tests -> elder.py 93.66%
- `test_hunt_coverage.py`: 40 tests -> hunt.py 95.68%
- `test_importer_coverage.py`: 34 tests -> importer.py 94.57%
- 4-module aggregate: 58.80% -> 94.55%

### Lint Cleanup
- Replaced 13 `try-except-pass` with `contextlib.suppress` (ruff SIM105)
- Moved imports to file top (ruff E402) in event_bus.py, orchestration.py
- Removed unused variables (ruff F841) in hunt.py
- Fixed mypy type annotations in event_bus.py, db.py, hunt.py, orchestration.py
- Updated .pre-commit-config.yaml: mypy reads pyproject.toml + `--follow-imports=silent`

### File Archiving
- 34 legacy .md reports moved to `docs/archive/` (4 subdirectories)
- Root .md count: 37 -> 3 (README, AUDIT_REPORT, BASELINE)
- `.gitignore` updated with .coverage, __pycache__, etc.

### Repo Cleanup
- Removed 1GB model file (SmolLM2-1.7B-Q4_K_M.gguf) from git history via filter-branch
- `.git` directory: 997MB -> 4.8MB (99.5% reduction)
- Deleted legacy tag `v1.0.0-f10-baseline` (non-standard naming)
- Deleted 3 stale feature branches
- Added `*.gguf`, `*.bin`, `models/`, test artifacts to `.gitignore`
- Line-ending normalization across all tracked files

### Dual-Platform Remote
- Gitee: `liao_liang_7514/frost-sop` (origin)
- GitHub: `llimage/frost-sop` (github)
- Push script: `push_v5_final.bat`

### Test Baseline
- Main suite: **1006 passed**, 7 skipped, 0 failed (exit code 0)
- Property + Benchmark: 24 passed, 0 failed
- Total: **1030 passed**

## [v3.0.0] - 2026-06-29

### Features
- NiceGUI cockpit (483 lines) with real FastAPI integration
- V5.0 Panel with DecisionFlow state machine
- Next.js frontend (parallel UI)
- P0 security hardening: SQL injection whitelist + CORS env var + deprecated app.py removal

## [v2.0.0] - 2026-06-26

### Features
- EventBus event bus (sync + async)
- Three-layer event subscription: ancestor/parent/elder
- Event persistence to event_log table
