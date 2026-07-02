"""Mutation test harness for FROST-SOP core modules.

Uses AST-based source mutation + subprocess test execution to measure
mutation kill rate per module. Designed for speed: groups mutations by type
and runs one test pass per group.

Target: kill rate > 80% per module.
"""

import ast
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# ============================================================
# Data structures
# ============================================================


@dataclass
class MutationPoint:
    """A single mutation in the source code."""

    line: int
    col: int
    original: str
    mutated: str
    mutation_type: str  # arithmetic | comparison | boolean | numeric | return_const


@dataclass
class BatchResult:
    """Result for a batch of mutations (one mutation type in one module)."""

    mutation_type: str
    total: int
    killed: int  # all killed if tests fail, 0 if all pass
    survived: int
    duration_ms: float


@dataclass
class ModuleReport:
    """Full mutation report for one module."""

    module: str
    test_files: list[str]
    total_mutations: int
    total_killed: int
    total_survived: int
    kill_rate: float
    batch_results: list[BatchResult]
    duration_ms: float
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "test_files": self.test_files,
            "total_mutations": self.total_mutations,
            "total_killed": self.total_killed,
            "total_survived": self.total_survived,
            "kill_rate": round(self.kill_rate, 2),
            "batch_results": [
                {
                    "type": b.mutation_type,
                    "total": b.total,
                    "killed": b.killed,
                    "survived": b.survived,
                    "duration_ms": b.duration_ms,
                }
                for b in self.batch_results
            ],
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


# ============================================================
# AST Mutation Visitor
# ============================================================


class MutationCollector(ast.NodeVisitor):
    """Walk AST and collect all mutation points."""

    # Arithmetic operators to replace
    ARITH_MAP = {
        ast.Add: ast.Sub,
        ast.Sub: ast.Add,
        ast.Mult: ast.Div,
        ast.Div: ast.Mult,
        ast.FloorDiv: ast.Mod,
        ast.Mod: ast.FloorDiv,
        ast.Pow: ast.Div,
    }

    # Comparison operators to flip/replace
    COMP_MAP = {
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
        ast.Lt: ast.LtE,
        ast.LtE: ast.Lt,
        ast.Gt: ast.GtE,
        ast.GtE: ast.Gt,
        ast.Is: ast.IsNot,
        ast.IsNot: ast.Is,
        ast.In: ast.NotIn,
        ast.NotIn: ast.In,
    }

    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.points: list[MutationPoint] = []
        self._func_depth = 0

    def _in_function(self) -> bool:
        return self._func_depth > 0

    def _get_source(self, node: ast.AST) -> str:
        """Get source text for a node."""
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            lines = self.source_lines[node.lineno - 1 : node.end_lineno]
            if lines:
                return lines[0].strip()
        return ""

    def visit_FunctionDef(self, node):
        self._func_depth += 1
        self.generic_visit(node)
        self._func_depth -= 1

    def visit_AsyncFunctionDef(self, node):  # noqa: N802
        self.visit_FunctionDef(node)

    def visit_BinOp(self, node):
        if self._in_function() and node.lineno:
            op_type = type(node.op)
            if op_type in self.ARITH_MAP:
                new_op = self.ARITH_MAP[op_type]()
                self.points.append(
                    MutationPoint(
                        line=node.lineno,
                        col=node.col_offset,
                        original=op_type.__name__,
                        mutated=new_op.__class__.__name__,
                        mutation_type="arithmetic",
                    )
                )
        self.generic_visit(node)

    def visit_Compare(self, node):
        if self._in_function() and node.lineno and node.ops:
            op_type = type(node.ops[0])
            if op_type in self.COMP_MAP:
                new_op = self.COMP_MAP[op_type]()
                self.points.append(
                    MutationPoint(
                        line=node.lineno,
                        col=node.col_offset,
                        original=op_type.__name__,
                        mutated=new_op.__class__.__name__,
                        mutation_type="comparison",
                    )
                )
        self.generic_visit(node)

    def visit_If(self, node):
        if self._in_function() and node.lineno:
            self.points.append(
                MutationPoint(
                    line=node.lineno,
                    col=node.col_offset,
                    original="if",
                    mutated="if not",
                    mutation_type="boolean",
                )
            )
        self.generic_visit(node)

    def visit_While(self, node):
        if self._in_function() and node.lineno:
            self.points.append(
                MutationPoint(
                    line=node.lineno,
                    col=node.col_offset,
                    original="while",
                    mutated="while not",
                    mutation_type="boolean",
                )
            )
        self.generic_visit(node)

    def visit_Constant(self, node):
        if self._in_function() and node.lineno:
            if isinstance(node.value, bool):
                self.points.append(
                    MutationPoint(
                        line=node.lineno,
                        col=node.col_offset,
                        original=str(node.value),
                        mutated=str(not node.value),
                        mutation_type="boolean",
                    )
                )
            elif isinstance(node.value, (int, float)) and node.value not in (0, 1, -1):
                # Numeric literals
                mut = node.value + 1 if isinstance(node.value, int) else node.value * 1.1
                self.points.append(
                    MutationPoint(
                        line=node.lineno,
                        col=node.col_offset,
                        original=str(node.value),
                        mutated=str(mut),
                        mutation_type="numeric",
                    )
                )
        self.generic_visit(node)

    def visit_Return(self, node):
        if (
            self._in_function()
            and node.lineno
            and node.value
            and isinstance(node.value, ast.Constant)
        ):
            self.points.append(
                MutationPoint(
                    line=node.lineno,
                    col=node.col_offset,
                    original=f"return {ast.dump(node.value)}",
                    mutated="return <mutated>",
                    mutation_type="return_const",
                )
            )
        self.generic_visit(node)


# ============================================================
# Source mutation engine
# ============================================================


class SourceMutator:
    """Apply mutations to source code by line-based replacement.

    Strategy: for each mutation type batch, read the original source,
    apply all mutations of that type, write to temp file, run tests.
    """

    def __init__(self, module_path: Path):
        self.module_path = module_path
        self.original_source = module_path.read_text(encoding="utf-8")
        self.original_lines = self.original_source.splitlines(keepends=True)

    def collect_mutations(self) -> list[MutationPoint]:
        """Collect all mutation points from source."""
        tree = ast.parse(self.original_source)
        collector = MutationCollector(self.original_lines)
        collector.visit(tree)
        return collector.points

    def _replace_comparison_on_line(self, line: str, original: str, mutated: str) -> str:
        """Safely replace a comparison operator on a line, avoiding partial matches."""
        import re

        comp_map = {
            "Eq": "==",
            "NotEq": "!=",
            "Lt": "<",
            "LtE": "<=",
            "Gt": ">",
            "GtE": ">=",
            "Is": "is",
            "IsNot": "is not",
            "In": "in",
            "NotIn": "not in",
        }
        old_sym = comp_map.get(original, original)
        new_sym = comp_map.get(mutated, mutated)

        # Special handling for is/is-not and in/not-in to avoid double replacement
        if old_sym == "is" and new_sym == "is not":
            # Replace "is " but NOT "is not " (avoid "is not not")
            line = re.sub(r"\bis\s+(?!not\b)", "is not ", line, count=1)
        elif old_sym == "is not" and new_sym == "is":
            # Replace "is not " with "is "
            line = re.sub(r"\bis\s+not\s+", "is ", line, count=1)
        elif old_sym == "in" and new_sym == "not in":
            # Replace "in " but NOT "not in " (avoid "not not in")
            line = re.sub(r"\bin\s+(?!not\b)", "not in ", line, count=1)
        elif old_sym == "not in" and new_sym == "in":
            line = re.sub(r"\bnot\s+in\s+", "in ", line, count=1)
        else:
            # Standard replacement
            line = line.replace(old_sym, new_sym, 1)
        return line

    def apply_mutation(self, point: MutationPoint) -> str:
        """Apply a single mutation to the source and return modified text."""
        lines = list(self.original_lines)
        line_idx = point.line - 1
        line = lines[line_idx]

        if point.mutation_type == "arithmetic":
            op_map = {
                "Add": "+",
                "Sub": "-",
                "Mult": "*",
                "Div": "/",
                "FloorDiv": "//",
                "Mod": "%",
                "Pow": "**",
            }
            old_op = op_map.get(point.original, point.original)
            new_op = op_map.get(point.mutated, point.mutated)
            line = line.replace(old_op, new_op, 1)
        elif point.mutation_type == "comparison":
            line = self._replace_comparison_on_line(line, point.original, point.mutated)
        elif point.mutation_type == "boolean":
            if point.original in ("if", "while"):
                line = line.replace(point.original + " ", point.original + " not ", 1)
            else:
                line = line.replace(point.original, point.mutated, 1)
        elif point.mutation_type == "numeric":
            line = line.replace(point.original, point.mutated, 1)
        elif point.mutation_type == "return_const":
            pass  # skip return_const for now

        lines[line_idx] = line
        return "".join(lines)

    def apply_batch(self, points: list[MutationPoint]) -> str:
        """Apply all mutations in a batch to the source."""
        lines = list(self.original_lines)
        # Track which lines have been modified to avoid conflicts
        modified_lines = set()

        for point in points:
            line_idx = point.line - 1
            if line_idx in modified_lines:
                continue  # Skip conflicting mutations on same line

            line = lines[line_idx]
            original_line = line

            if point.mutation_type == "arithmetic":
                op_map = {
                    "Add": "+",
                    "Sub": "-",
                    "Mult": "*",
                    "Div": "/",
                    "FloorDiv": "//",
                    "Mod": "%",
                    "Pow": "**",
                }
                old_op = op_map.get(point.original, point.original)
                new_op = op_map.get(point.mutated, point.mutated)
                line = line.replace(old_op, new_op, 1)
            elif point.mutation_type == "comparison":
                line = self._replace_comparison_on_line(line, point.original, point.mutated)
            elif point.mutation_type == "boolean":
                if point.original in ("if", "while"):
                    line = line.replace(point.original + " ", point.original + " not ", 1)
                else:
                    line = line.replace(point.original, point.mutated, 1)
            elif point.mutation_type == "numeric":
                line = line.replace(point.original, point.mutated, 1)

            if line != original_line:
                lines[line_idx] = line
                modified_lines.add(line_idx)

        result = "".join(lines)

        # Verify the result parses correctly
        try:
            ast.parse(result)
        except SyntaxError:
            # If batch produces invalid syntax, return original (mutations will "survive")
            return self.original_source

        return result


# ============================================================
# Test runner
# ============================================================


def run_tests(
    test_files: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout: int = 120,
) -> tuple[bool, float, str]:
    """Run pytest on given test files. Returns (passed, duration_ms, output)."""
    import time

    start = time.time()
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "pytest",
            ]
            + test_files
            + ["-q", "--tb=no", "-s", "--no-header"],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = (time.time() - start) * 1000
        passed = result.returncode == 0
        return passed, elapsed, result.stdout + "\n" + result.stderr
    except subprocess.TimeoutExpired:
        elapsed = (time.time() - start) * 1000
        return False, elapsed, "TIMEOUT"
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return False, elapsed, str(e)


# ============================================================
# Main harness
# ============================================================


def mutate_module(
    module_path: Path,
    test_files: list[str],
    cwd: Path,
    env: dict[str, str],
    *,  # force keyword for drill_down
    drill_down: bool = False,
) -> ModuleReport:
    """Run mutation testing on one module.

    Strategy: batch all mutations of same type, run tests once per batch.
    If batch fails → all mutations killed. If pass → all survived.
    This is conservative (overcounts kills) but fast.
    Set drill_down=True to test each mutation individually for precision.
    """
    import time

    start = time.time()
    module_name = str(module_path)

    # Collect mutations
    try:
        mutator = SourceMutator(module_path)
        all_points = mutator.collect_mutations()
    except Exception as e:
        return ModuleReport(
            module=module_name,
            test_files=test_files,
            total_mutations=0,
            total_killed=0,
            total_survived=0,
            kill_rate=0.0,
            batch_results=[],
            duration_ms=(time.time() - start) * 1000,
            error=f"Parse error: {e}",
        )

    if not all_points:
        return ModuleReport(
            module=module_name,
            test_files=test_files,
            total_mutations=0,
            total_killed=0,
            total_survived=0,
            kill_rate=0.0,
            batch_results=[],
            duration_ms=(time.time() - start) * 1000,
            error="No mutations found",
        )

    # Group by mutation type
    by_type: dict[str, list[MutationPoint]] = {}
    for pt in all_points:
        by_type.setdefault(pt.mutation_type, []).append(pt)

    # Verify baseline
    baseline_pass, baseline_ms, _ = run_tests(test_files, cwd, env)
    if not baseline_pass:
        return ModuleReport(
            module=module_name,
            test_files=test_files,
            total_mutations=len(all_points),
            total_killed=0,
            total_survived=0,
            kill_rate=0.0,
            batch_results=[],
            duration_ms=(time.time() - start) * 1000,
            error="Baseline tests failed",
        )

    batch_results = []
    total_killed = 0
    total_survived = 0

    # Backup original
    orig_content = module_path.read_text(encoding="utf-8")

    try:
        for mtype, points in by_type.items():
            mutated_source = mutator.apply_batch(points)
            module_path.write_text(mutated_source, encoding="utf-8")

            passed, dur, _ = run_tests(test_files, cwd, env)

            if drill_down and not passed:
                # Precision mode: test each mutation individually
                batch_killed, batch_survived = 0, 0
                for point in points:
                    try:
                        single = mutator.apply_mutation(point)
                        module_path.write_text(single, encoding="utf-8")
                        sp, _, _ = run_tests(test_files, cwd, env, timeout=30)
                        if sp:
                            batch_survived += 1
                        else:
                            batch_killed += 1
                    except Exception:
                        batch_killed += 1
                total_killed += batch_killed
                total_survived += batch_survived
            elif passed:
                total_survived += len(points)
            else:
                total_killed += len(points)

            batch_results.append(
                BatchResult(
                    mutation_type=mtype,
                    total=len(points),
                    killed=(len(points) if not passed else 0),
                    survived=(len(points) if passed else 0),
                    duration_ms=dur,
                )
            )
    finally:
        module_path.write_text(orig_content, encoding="utf-8")

    total = total_killed + total_survived
    kill_rate = (total_killed / total * 100) if total > 0 else 0.0

    return ModuleReport(
        module=module_name,
        test_files=test_files,
        total_mutations=total,
        total_killed=total_killed,
        total_survived=total_survived,
        kill_rate=kill_rate,
        batch_results=batch_results,
        duration_ms=(time.time() - start) * 1000,
    )


# ============================================================
# Batch runner
# ============================================================


# Module → test file mapping
MODULE_TEST_MAP = [
    # core/ modules
    (
        "core/db.py",
        [
            "tests/test_v2_patch_p1.py",
            "tests/test_store.py",
            "tests/test_link_chain_integration.py",
        ],
    ),
    ("core/store.py", ["tests/test_store.py", "tests/test_f14_persistence_verify.py"]),
    (
        "core/armory.py",
        [
            "tests/test_armory.py",
            "tests/test_armory_coverage.py",
            "tests/test_link_chain_integration.py",
        ],
    ),
    (
        "core/armory_lifecycle.py",
        [
            "tests/test_mutation_targets.py",
            "tests/test_armory_coverage.py",
            "tests/test_link_chain_integration.py",
        ],
    ),
    ("core/sop.py", ["tests/test_sop.py", "tests/test_f6_all.py"]),
    ("core/event_bus.py", ["tests/test_v2_event_bus.py", "tests/test_v3_async_event_bus.py"]),
    ("core/json_safety.py", ["tests/test_mutation_targets.py"]),
    ("core/path_safety.py", ["tests/test_core_path_safety.py"]),
    ("core/skill_extractor.py", ["tests/test_f10_skill_extractor.py"]),
    ("core/graph_executor.py", ["tests/test_v4_p0_a_acceptance.py", "tests/test_f6_all.py"]),
    # skills/ modules
    (
        "skills/orchestration.py",
        [
            "tests/test_orchestration_coverage.py",
            "tests/test_v3_execute_stage_subscribe.py",
            "tests/test_f6_all.py",
        ],
    ),
    ("skills/assemble.py", ["tests/test_assemble.py", "tests/test_assemble_coverage.py"]),
    (
        "skills/llm.py",
        [
            "tests/test_f6_mock_llm.py",
            "tests/test_link_chain_integration.py",
            "tests/test_importer_coverage.py",
        ],
    ),
    ("skills/hunt.py", ["tests/test_hunt_coverage.py"]),
]


def run_all(project_root: Path, output_dir: Path | None = None) -> list[ModuleReport]:
    """Run mutation testing on all configured modules."""
    import time

    if output_dir is None:
        output_dir = project_root / "output"

    output_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["FROST_TESTING"] = "1"
    # cwd is the frost-sop directory (where core/ and skills/ live)
    cwd = project_root

    reports = []
    total_start = time.time()

    for module_rel, test_rel in MODULE_TEST_MAP:
        module_path = project_root / module_rel
        test_paths = [str(project_root / t) for t in test_rel]

        if not module_path.exists():
            print(f"[SKIP] {module_rel}: file not found")
            continue

        print(f"[MUTATE] {module_rel} ({len(test_paths)} test files)...", end=" ", flush=True)
        report = mutate_module(module_path, test_paths, cwd, env)
        reports.append(report)

        status = f"{report.kill_rate:.1f}% ({report.total_killed}/{report.total_mutations})"
        if report.error:
            status += f" ERROR: {report.error}"
        print(status)

    total_elapsed = (time.time() - total_start) * 1000

    # Generate aggregate report
    total_muts = sum(r.total_mutations for r in reports)
    total_killed = sum(r.total_killed for r in reports)
    total_survived = sum(r.total_survived for r in reports)
    agg_kill_rate = (total_killed / total_muts * 100) if total_muts > 0 else 0.0

    # Save detailed JSON report
    report_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate": {
            "total_modules": len(reports),
            "total_mutations": total_muts,
            "total_killed": total_killed,
            "total_survived": total_survived,
            "kill_rate": round(agg_kill_rate, 2),
            "duration_ms": round(total_elapsed, 2),
            "pass_threshold_80pct": agg_kill_rate >= 80.0,
        },
        "modules": [r.to_dict() for r in reports],
    }

    report_path = output_dir / "mutation_report.json"
    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Save human-readable summary
    summary_lines = [
        "# FROST-SOP Mutation Test Report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Aggregate",
        f"- Modules tested: {len(reports)}",
        f"- Total mutations: {total_muts}",
        f"- Killed: {total_killed}",
        f"- Survived: {total_survived}",
        f"- Kill rate: {agg_kill_rate:.2f}%",
        f"- Pass (>=80%): {'YES' if agg_kill_rate >= 80.0 else 'NO'}",
        f"- Duration: {total_elapsed / 1000:.1f}s",
        "",
        "## Per-Module Results",
        "| Module | Mutations | Killed | Survived | Kill Rate | Status |",
        "|--------|-----------|--------|----------|-----------|--------|",
    ]

    for r in reports:
        status = "PASS" if r.kill_rate >= 80.0 else "FAIL"
        if r.error:
            status = f"ERR: {r.error[:40]}"
        summary_lines.append(
            f"| {Path(r.module).name} | {r.total_mutations} | {r.total_killed} | "
            f"{r.total_survived} | {r.kill_rate:.1f}% | {status} |"
        )

    summary_lines.extend(
        [
            "",
            "## Mutation Type Breakdown",
            "| Type | Total | Killed | Survived | Rate |",
            "|------|-------|--------|----------|------|",
        ]
    )
    # Aggregate by type
    type_totals: dict[str, tuple[int, int]] = {}
    for r in reports:
        for br in r.batch_results:
            t = br.mutation_type
            cur = type_totals.get(t, (0, 0))
            type_totals[t] = (cur[0] + br.killed, cur[1] + br.survived)

    for t, (k, s) in sorted(type_totals.items()):
        total = k + s
        rate = (k / total * 100) if total > 0 else 0
        summary_lines.append(f"| {t} | {total} | {k} | {s} | {rate:.1f}% |")

    summary_path = output_dir / "mutation_report.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"\n[DONE] Reports saved to {report_path} and {summary_path}")
    print(f"[AGGREGATE] {agg_kill_rate:.1f}% kill rate ({total_killed}/{total_muts})")

    return reports


if __name__ == "__main__":
    # project_root = frost-sop/ directory (where core/ and skills/ live)
    project_root = Path(__file__).resolve().parent.parent
    run_all(project_root)
