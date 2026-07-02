# FROST-SOP Mutation Test Report (P1 扩展)

Generated: 2026-07-02T13:00:00+08:00
Tool: Custom AST-based mutation harness (tests/mutation_harness.py)
Previous: cosmic-ray v8.4.6, 1 module only, 52.44% kill rate (F rating)

## Aggregate

| Metric | Value |
|--------|-------|
| Modules tested | **14** (was 1) |
| Total mutations | **950** |
| Killed | **690** |
| Survived | **260** |
| **Kill rate** | **72.6%** (was 52.44%) |
| Modules ≥ 80% | **10 / 14** |
| Pass threshold (≥80%) | **NO** (4 modules below) |
| Duration | ~8 min |

## Per-Module Results

| # | Module | Mutations | Killed | Survived | Kill Rate | Status |
|---|--------|-----------|--------|----------|-----------|--------|
| 1 | core/db.py | 58 | 53 | 5 | 91.4% | ✅ PASS |
| 2 | core/store.py | 48 | 46 | 2 | 95.8% | ✅ PASS |
| 3 | core/armory.py | 130 | 90 | 40 | 69.2% | ❌ FAIL |
| 4 | core/armory_lifecycle.py | 101 | 90 | 11 | 89.1% | ✅ PASS |
| 5 | core/sop.py | 10 | 10 | 0 | 100.0% | ✅ PASS |
| 6 | core/event_bus.py | 96 | 80 | 16 | 83.3% | ✅ PASS |
| 7 | core/json_safety.py | 18 | 17 | 1 | 94.4% | ✅ PASS |
| 8 | core/path_safety.py | 8 | 8 | 0 | 100.0% | ✅ PASS |
| 9 | core/skill_extractor.py | 57 | 27 | 30 | 47.4% | ❌ FAIL |
| 10 | core/graph_executor.py | 61 | 35 | 26 | 57.4% | ❌ FAIL |
| 11 | skills/orchestration.py | 95 | 85 | 10 | 89.5% | ✅ PASS |
| 12 | skills/assemble.py | 45 | 45 | 0 | 100.0% | ✅ PASS |
| 13 | skills/llm.py | 163 | 53 | 110 | 32.5% | ❌ FAIL |
| 14 | skills/hunt.py | 60 | 51 | 9 | 85.0% | ✅ PASS |

## Mutation Type Breakdown

| Type | Total | Killed | Survived | Kill Rate |
|------|-------|--------|----------|-----------|
| boolean (if/while/True/False flip) | 321 | 296 | 25 | 92.2% |
| comparison (==/!=/</>/is/in flip) | 197 | 86 | 111 | 43.7% |
| arithmetic (+/-/*// swap) | 25 | 15 | 10 | 60.0% |
| numeric (literal +1/*1.1) | 68 | 8 | 60 | 11.8% |
| return_const (return value mutation) | 42 | 0 | 42 | 0.0% |

## Analysis

### Strengths (kill rate ≥ 80%)
- **Boolean mutations**: 92.2% kill rate — `if`/`while` condition flips and `True`/`False` swaps are well-covered
- **10/14 modules pass** the 80% threshold, including all critical data-layer modules (db, store, sop)
- **3 modules at 100%**: sop.py, path_safety.py, assemble.py

### Weaknesses (kill rate < 80%)

| Module | Kill Rate | Root Cause |
|--------|-----------|------------|
| skills/llm.py | 32.5% | FROST_TESTING mock mode bypasses real API code; comparison/numeric/return mutations in uncalled paths survive |
| core/skill_extractor.py | 47.4% | Test coverage focuses on boolean paths; comparison and numeric mutations in edge cases not caught |
| core/graph_executor.py | 57.4% | Comparison mutations in decision node logic not exercised by current tests |
| core/armory.py | 69.2% | Numeric mutations in health score calculations survive; test_armory_coverage mocks some paths |

### Mutation Type Gaps
- **return_const (0%)**: Return value mutations are not caught by any test. Tests verify side effects but not specific return values in many cases.
- **numeric (11.8%)**: Numeric literal mutations (e.g., threshold values) are rarely caught. Tests don't assert specific numeric outcomes.
- **comparison (43.7%)**: Many comparison operator flips survive, especially in modules where mock mode bypasses the comparison logic.

## Comparison with Previous Audit

| Metric | Before (cosmic-ray) | After (this report) |
|--------|---------------------|---------------------|
| Modules covered | 1 (monitor.py) | **14** (all core + key skills) |
| Kill rate | 52.44% | **72.6%** |
| Mutation types | 1 (ReplaceBinaryOperator) | **5** (boolean/comparison/arithmetic/numeric/return) |
| Rating | F | **C** (improved, but below 80% target) |

## Improvement Path

To reach >80% aggregate kill rate:
1. **llm.py** (+30% impact): Add tests that exercise non-mock code paths (API key validation, error handling, budget checks)
2. **skill_extractor.py** (+15% impact): Add comparison assertion tests for extraction logic edge cases
3. **graph_executor.py** (+12% impact): Add decision node comparison tests
4. **armory.py** (+10% impact): Add health score calculation assertion tests

## Files

- `tests/mutation_harness.py` — AST-based mutation test framework
- `tests/test_mutation_targets.py` — 67 targeted tests for json_safety + armory_lifecycle
- `output/mutation_report.json` — Machine-readable detailed results
- `output/mutation_report.md` — This report
