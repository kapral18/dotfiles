#!/usr/bin/env python3
"""Affected-first repo check orchestrator.

Default: lint, verify gates, and tests for paths dirty vs HEAD (plus untracked).
``--staged`` limits that set to the index (pre-commit).

Affected tests are the union of: filename convention, one-hop Python imports
among ``scripts/*.py``, and ``TEST_RULES``. Slow picker shards run only from
those rules (or from editing the shard itself), never from import fan-out.
``--full`` is human-only and requires ``CHECK_FULL=1``. Agents must not use it.

Usage:
    python3 scripts/check.py
    python3 scripts/check.py --staged
    python3 scripts/check.py --print-plan
    CHECK_FULL=1 python3 scripts/check.py --full
"""

from __future__ import annotations

import argparse
import ast
import functools
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent


@dataclass(frozen=True)
class Gate:
    name: str
    argv: tuple[str, ...]
    prefixes: tuple[str, ...] = ()
    suffixes: tuple[str, ...] = ()
    on_add_delete: bool = False


@dataclass(frozen=True)
class TestRule:
    prefixes: tuple[str, ...]
    tests: tuple[str, ...]


@dataclass(frozen=True)
class ExtraTest:
    name: str
    argv: tuple[str, ...]
    prefixes: tuple[str, ...]
    env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CheckJob:
    name: str
    argv: tuple[str, ...]
    env: dict[str, str] | None = None


@dataclass(frozen=True)
class CheckPlan:
    mode: str
    changed: tuple[str, ...]
    fmt_paths: tuple[str, ...]
    ruff_paths: tuple[str, ...]
    gates: tuple[str, ...]
    tests: tuple[str, ...]
    extra: tuple[str, ...]

    def as_json(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "changed": list(self.changed),
            "fmt": list(self.fmt_paths),
            "ruff": list(self.ruff_paths),
            "gates": list(self.gates),
            "tests": list(self.tests),
            "extra": list(self.extra),
        }


GATES: tuple[Gate, ...] = (
    Gate(
        name="verify-templates",
        argv=("python3", "scripts/verify_templates.py"),
        prefixes=("home/.chezmoidata/", "home/.chezmoitemplates/", "scripts/verify_templates.py"),
        suffixes=(".tmpl",),
    ),
    Gate(
        name="verify-mermaids",
        argv=("python3", "scripts/verify_mermaids.py"),
        prefixes=(".mermaids/", "scripts/verify_mermaids.py"),
        on_add_delete=True,
    ),
    Gate(
        name="verify-bin-surface",
        argv=("python3", "scripts/verify_bin_surface.py"),
        prefixes=(
            "home/exact_bin/",
            "home/exact_lib/",
            "home/dot_config/fish/completions/",
            "docs/topics/workflow/custom-commands/",
            ".mermaids/07c-bin-commands.mmd",
            "scripts/verify_bin_surface.py",
        ),
    ),
    Gate(
        name="verify-docs-navigation",
        argv=("python3", "scripts/verify_docs_navigation.py"),
        prefixes=("docs/", "website/", "scripts/verify_docs_navigation.py"),
    ),
    Gate(
        name="verify-agent-file-sizes",
        argv=("python3", "scripts/verify_agent_file_sizes.py"),
        prefixes=("home/exact_dot_agents/", "scripts/verify_agent_file_sizes.py"),
    ),
    Gate(
        name="verify-agent-policy",
        argv=(
            "python3",
            "scripts/compile_ai_policy.py",
            "audit-coverage",
            "--legacy",
            "home/readonly_AGENTS.md",
            "--base-ref",
            "origin/main",
        ),
        prefixes=(
            "home/readonly_AGENTS.md",
            "home/dot_config/ai/exact_policy-ir/",
            "scripts/compile_ai_policy.py",
            "scripts/ai_policy_ir.py",
            "scripts/ai_harness_capabilities.py",
            "scripts/eval_ai_policy.py",
        ),
    ),
    Gate(
        name="verify-agent-policy-budgets",
        argv=(
            "python3",
            "scripts/compile_ai_policy.py",
            "verify-budgets",
            "--core-max-bytes",
            "999999",
            "--overlay-max-bytes",
            "8192",
            "--skill-max-bytes",
            "8192",
            "--description-total-max-bytes",
            "4096",
        ),
        prefixes=(
            "home/readonly_AGENTS.md",
            "home/dot_config/ai/exact_policy-ir/",
            "scripts/compile_ai_policy.py",
            "scripts/ai_policy_ir.py",
            "scripts/ai_harness_capabilities.py",
        ),
    ),
)

TEST_RULES: tuple[TestRule, ...] = (
    TestRule(
        prefixes=(
            "home/dot_config/exact_tmux/exact_scripts/pickers/",
            "home/dot_config/exact_tmux/exact_scripts/pick_url/",
            "home/dot_config/exact_tmux/exact_conf.d/readonly_41-pickers.conf",
            "home/dot_config/exact_tmux/exact_conf.d/readonly_90-plugins.conf",
        ),
        tests=(
            "tests/test_tmux_pickers.py",
            "tests/test_gh_picker_dispatch_state.py",
            "tests/test_gh_picker_lock.py",
            "tests/test_gh_picker_review_requests.py",
            "tests/test_tmux_handoff_lifecycle.py",
            "tests/test_tmux_handoff_namespace.py",
            "tests/test_session_github_cache.py",
            "tests/test_plain_session_removal.py",
        ),
    ),
    TestRule(
        prefixes=(
            "home/exact_dot_agents/exact_hooks/executable_",
            "home/exact_dot_agents/exact_hooks/hook_common.py",
            "home/exact_dot_agents/exact_hooks/correction_detector.py",
            "home/exact_dot_agents/exact_hooks/spec_mirror.py.tmpl",
            "home/exact_dot_agents/exact_hooks/worklog_queue.py.tmpl",
            "scripts/worklog_queue.py",
            "scripts/session_context.py",
            "scripts/perturn_recall.py",
            "scripts/spec_mirror.py",
        ),
        tests=(
            "tests/test_agent_hooks.py",
            "tests/test_recall_worklog.py",
            "tests/test_premise_nudge.py",
            "tests/test_correction_detector.py",
            "tests/test_model_band_invariants.py",
            "tests/test_agent_skill_invariants.py",
        ),
    ),
    TestRule(
        prefixes=("scripts/tests/bin_command_support.py",),
        tests=(
            "tests/test_w_issue.py",
            "tests/test_artifact.py",
            "tests/test_unwrap_md.py",
            "tests/test_mcp_token.py",
            "tests/test_openrouter_wrappers.py",
            "tests/test_install_yarn_pkgs.py",
            "tests/test_copilot.py",
            "tests/test_codex.py",
            "tests/test_cursor_llama_cpp.py",
            "tests/test_cursor.py",
            "tests/test_kbn_stack.py",
        ),
    ),
    TestRule(
        prefixes=(
            "home/exact_bin/executable_,claude-openrouter",
            "home/exact_bin/executable_,codex-openrouter",
            "home/exact_bin/executable_,copilot-openrouter",
            "home/exact_bin/executable_,cursor-openrouter",
            "home/exact_lib/exact_shared/executable_openrouter_presets.py",
        ),
        tests=("tests/test_openrouter_wrappers.py",),
    ),
    TestRule(
        prefixes=(
            "home/exact_bin/executable_,claude-llama-cpp",
            "home/exact_bin/executable_,codex-llama-cpp",
            "home/exact_bin/executable_,cursor-llama-cpp",
            "home/exact_bin/executable_,opencode-llama-cpp",
            "home/dot_config/fish/completions/readonly_,claude-llama-cpp.fish",
            "home/dot_config/fish/completions/readonly_,codex-llama-cpp.fish",
            "home/dot_config/fish/completions/readonly_,cursor-llama-cpp.fish",
            "home/dot_config/fish/completions/readonly_,opencode-llama-cpp.fish",
        ),
        tests=("tests/test_cursor_llama_cpp.py",),
    ),
    TestRule(
        prefixes=(
            "home/.chezmoidata/ai_models/",
            "home/dot_config/llama.cpp/",
            "home/dot_codex/readonly_llama-cpp-model-catalog.json.tmpl",
            "home/dot_pi/agent/readonly_models.json",
            "home/dot_pi/agent/readonly_models.personal.json",
            "home/readonly_dot_default-llama-cpp-models.tmpl",
            "scripts/ai_models.py",
            "scripts/model_mirrors.py",
        ),
        tests=(
            "test_ai_launcher.py",
            "test_ai_models.py",
            "test_model_mirrors.py",
            "tests/test_model_band_invariants.py",
            "tests/test_invariants.py",
        ),
    ),
    TestRule(
        prefixes=(
            "home/readonly_AGENTS.md",
            "home/dot_config/exact_tmux/agent_prompts/prefix.txt",
            "home/dot_config/ai/exact_policy-ir/",
            "docs/topics/ai-assistants/system-prompt/source-of-truth.md",
        ),
        tests=("tests/test_sop_policy_invariants.py", "test_ai_policy_compiler.py"),
    ),
    TestRule(
        prefixes=(
            "home/exact_dot_agents/exact_skills/",
            "home/exact_dot_agents/exact_references/",
            "home/dot_pi/",
            "home/dot_claude/",
            "home/dot_codex/",
            "home/dot_omp/",
            "home/private_dot_copilot/",
            "home/dot_config/opencode/",
            "home/dot_config/exact_nvim/",
            "home/.chezmoiscripts/",
        ),
        tests=(
            "tests/test_agent_skill_invariants.py",
            "tests/test_review_policy_invariants.py",
            "tests/test_model_band_invariants.py",
            "tests/test_invariants.py",
        ),
    ),
    TestRule(prefixes=(".githooks/pre-commit", "bin/fmt", "bin/check"), tests=("test_pre_commit.py",)),
    TestRule(
        prefixes=("scripts/check.py", "scripts/test_runner.py", "Makefile", "AGENTS.md"), tests=("test_check.py",)
    ),
    TestRule(
        prefixes=("home/exact_lib/exact_,w/", "home/exact_bin/executable_,w"),
        tests=("tests/test_w_remove_detached.py", "tests/test_worktree_delete_boundaries.py"),
    ),
    TestRule(
        prefixes=("home/exact_lib/exact_,git/", "home/exact_bin/executable_,git"), tests=("tests/test_git_gate.py",)
    ),
    TestRule(prefixes=("home/exact_lib/exact_,proof/",), tests=("tests/test_proof_cli.py",)),
    TestRule(prefixes=("home/exact_lib/exact_,wh/",), tests=("tests/test_wh.py",)),
    TestRule(prefixes=("home/exact_lib/exact_,codex-adapter/",), tests=("tests/test_codex_adapter.py",)),
    TestRule(prefixes=("home/exact_lib/exact_,copilot-adapter/",), tests=("tests/test_copilot_adapter.py",)),
    TestRule(prefixes=("home/exact_lib/exact_,cursor-agent-shim/",), tests=("tests/test_cursor_agent_shim.py",)),
    TestRule(prefixes=("home/exact_lib/exact_,ai/", "home/exact_bin/executable_,ai"), tests=("test_ai_launcher.py",)),
    TestRule(prefixes=("home/dot_omp/",), tests=("test_omp_migration.py", "tests/test_invariants.py")),
    TestRule(prefixes=("scripts/install_github_zip_bundle.py",), tests=("tests/test_install_github_zip_bundle.py",)),
    TestRule(
        prefixes=(
            "home/dot_config/llama.cpp/",
            "scripts/sync_llama_cpp_models.py",
            "home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl",
        ),
        tests=("tests/test_llama_cpp_lifecycle.py",),
    ),
    TestRule(
        prefixes=("scripts/compile_ai_policy.py", "scripts/ai_policy_ir.py"),
        tests=("tests/test_ai_policy_compiler.py",),
    ),
)

EXTRA_TESTS: tuple[ExtraTest, ...] = (
    ExtraTest(
        name="fish-history-merge",
        argv=("python3", "home/exact_lib/exact_,history-sync/fish-history-merge.test.py", "-v"),
        prefixes=("home/exact_lib/exact_,history-sync/",),
    ),
    ExtraTest(
        name="copilot-agent-memory-extension",
        argv=("node", "scripts/tests/copilot_agent_memory_extension.test.mjs"),
        prefixes=(
            "scripts/tests/copilot_agent_memory_extension.test.mjs",
            "home/private_dot_copilot/exact_extensions/exact_agent-memory/",
        ),
        env=(("COPILOT_AGENT_MEMORY_EXTENSION_TEST", "1"),),
    ),
)

RUFF_PREFIXES = ("scripts/", "home/exact_lib/")
NOT_TEST_SHARDS = frozenset({"test_runner.py", "test_bin_commands.py"})
FULL_ALLOW_ENV = "CHECK_FULL"
# These shards dominate wall-clock (fzf listen / long batch waits). They run
# only from TEST_RULES or from editing the shard itself, never from fan-out.
SLOW_SHARDS = frozenset(
    {
        "tests/test_tmux_pickers.py",
        "tests/test_gh_picker_dispatch_state.py",
    }
)
SHARED_INFRA = ("scripts/_test_support.py",)


def _rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _matches(path: str, prefixes: tuple[str, ...], suffixes: tuple[str, ...] = ()) -> bool:
    path = _rel(path)
    for prefix in prefixes:
        needle = _rel(prefix)
        if path == needle.rstrip("/") or path.startswith(needle):
            return True
    return any(path.endswith(suffix) for suffix in suffixes)


def collect_changed(repo: Path, *, staged: bool) -> tuple[tuple[str, ...], bool]:
    """Return (changed relative paths, had_add_or_delete)."""
    if staged:
        names = _git(repo, ["diff", "--cached", "--name-only", "--diff-filter=ACMRD"])
        statuses = _git(repo, ["diff", "--cached", "--name-status", "--diff-filter=ACMRD"])
    else:
        names = _git(repo, ["diff", "--name-only", "HEAD"])
        untracked = _git(repo, ["ls-files", "--others", "--exclude-standard"])
        names = tuple(dict.fromkeys((*names, *untracked)))
        statuses = _git(repo, ["diff", "--name-status", "HEAD"])
        add_delete = any(line[:1] in {"A", "D", "R"} for line in statuses) or bool(untracked)
        return names, add_delete
    add_delete = any(line[:1] in {"A", "D", "R"} for line in statuses)
    return names, add_delete


def _git(repo: Path, args: list[str]) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = tuple(line.replace("\\", "/") for line in result.stdout.splitlines() if line.strip())
    return lines


def _convention_tests(path: str, repo: Path) -> tuple[str, ...]:
    path = _rel(path)
    found: list[str] = []
    if path.startswith("scripts/tests/") and Path(path).name.startswith("test_") and path.endswith(".py"):
        found.append(path[len("scripts/") :])
    elif path.startswith("scripts/") and Path(path).name.startswith("test_") and path.endswith(".py"):
        found.append(Path(path).name)
    elif path.startswith("scripts/") and not path.startswith("scripts/tests/"):
        name = Path(path).name
        if not name.startswith("test_") and name != "_test_support.py":
            stem = Path(name).stem
            for candidate in (f"test_{stem}.py", f"tests/test_{stem}.py"):
                if (repo / "scripts" / candidate).is_file():
                    found.append(candidate)
    marker = "home/exact_lib/exact_,"
    if path.startswith(marker):
        rest = path[len(marker) :]
        slug = rest.split("/", 1)[0].replace("-", "_")
        candidate = f"tests/test_{slug}.py"
        if (repo / "scripts" / candidate).is_file():
            found.append(candidate)
    if path.startswith("home/exact_bin/"):
        name = Path(path).name
        for prefix in ("executable_", "readonly_", "symlink_"):
            if name.startswith(prefix):
                name = name[len(prefix) :]
                break
        if name.startswith(","):
            name = name[1:]
        stem = name.split(".")[0].replace("-", "_")
        candidate = f"tests/test_{stem}.py"
        if (repo / "scripts" / candidate).is_file():
            found.append(candidate)
    return tuple(found)


def _imported_top_levels(source: str) -> frozenset[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return frozenset()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".", 1)[0])
    return frozenset(names)


@functools.lru_cache(maxsize=1)
def _import_index(repo_str: str) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    """Return (production_importers, test_importers) for top-level scripts/*.py modules."""
    repo = Path(repo_str)
    scripts = repo / "scripts"
    local = {
        path.stem
        for path in scripts.glob("*.py")
        if not path.name.startswith("test_") and path.name != "_test_support.py"
    }
    prod: dict[str, list[str]] = {name: [] for name in local}
    tests: dict[str, list[str]] = {name: [] for name in local}
    for path in sorted(scripts.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        imported = _imported_top_levels(path.read_text(encoding="utf-8")) & local
        rel = f"scripts/{path.name}"
        for name in imported:
            prod[name].append(rel)
    for path in sorted(scripts.glob("test_*.py")) + sorted((scripts / "tests").glob("test_*.py")):
        if path.name in NOT_TEST_SHARDS:
            continue
        imported = _imported_top_levels(path.read_text(encoding="utf-8")) & local
        rel = path.relative_to(scripts).as_posix()
        for name in imported:
            tests[name].append(rel)
    return (
        {name: tuple(paths) for name, paths in prod.items() if paths},
        {name: tuple(paths) for name, paths in tests.items() if paths},
    )


def _import_tests(path: str, repo: Path) -> tuple[str, ...]:
    path = _rel(path)
    if not path.startswith("scripts/") or not path.endswith(".py") or path.startswith("scripts/tests/"):
        return ()
    name = Path(path).name
    if name.startswith("test_") or name == "_test_support.py":
        return ()
    mod = Path(name).stem
    prod_importers, test_importers = _import_index(str(repo))
    found: list[str] = []
    found.extend(test_importers.get(mod, ()))
    for importer in prod_importers.get(mod, ()):
        found.extend(_convention_tests(importer, repo))
    return tuple(item for item in found if item not in SLOW_SHARDS)


def _shared_infra_tests(path: str, repo: Path) -> tuple[str, ...]:
    if not _matches(path, SHARED_INFRA):
        return ()
    return tuple(
        rel
        for rel in (item.relative_to(repo / "scripts").as_posix() for item in _discover_tests(repo))
        if rel not in SLOW_SHARDS
    )


def _existing_tests(repo: Path, tests: tuple[str, ...]) -> tuple[str, ...]:
    out: list[str] = []
    for rel in tests:
        rel = rel.replace("\\", "/")
        if Path(rel).name in NOT_TEST_SHARDS:
            continue
        if (repo / "scripts" / rel).is_file():
            out.append(rel)
    return tuple(dict.fromkeys(out))


def plan_check(
    repo: Path,
    *,
    full: bool,
    changed: tuple[str, ...],
    add_delete: bool,
) -> CheckPlan:
    if full:
        tests = tuple(path.relative_to(repo / "scripts").as_posix() for path in _discover_tests(repo))
        return CheckPlan(
            mode="full",
            changed=changed,
            fmt_paths=(),
            ruff_paths=("scripts/", "home/exact_lib/"),
            gates=tuple(gate.name for gate in GATES),
            tests=tests,
            extra=tuple(extra.name for extra in EXTRA_TESTS),
        )

    fmt_paths = tuple(path for path in changed if (repo / path).is_file())
    ruff_paths = tuple(path for path in fmt_paths if path.endswith(".py") and _matches(path, RUFF_PREFIXES))
    gates = tuple(
        gate.name
        for gate in GATES
        if (gate.on_add_delete and add_delete) or any(_matches(path, gate.prefixes, gate.suffixes) for path in changed)
    )
    selected: list[str] = []
    for path in changed:
        selected.extend(_convention_tests(path, repo))
        selected.extend(_import_tests(path, repo))
        selected.extend(_shared_infra_tests(path, repo))
        for rule in TEST_RULES:
            if _matches(path, rule.prefixes):
                selected.extend(rule.tests)
    tests = _existing_tests(repo, tuple(selected))
    extra = tuple(item.name for item in EXTRA_TESTS if any(_matches(path, item.prefixes) for path in changed))
    return CheckPlan(
        mode="affected",
        changed=changed,
        fmt_paths=fmt_paths,
        ruff_paths=ruff_paths,
        gates=gates,
        tests=tests,
        extra=extra,
    )


def production_probe_paths(repo: Path) -> tuple[str, ...]:
    """Paths that must be enough to select every live shard (orphan census)."""
    probes: list[str] = []
    for rule in TEST_RULES:
        probes.extend(rule.prefixes)
    for extra in EXTRA_TESTS:
        probes.extend(extra.prefixes)
    probes.extend(SHARED_INFRA)
    scripts = repo / "scripts"
    for path in sorted(scripts.iterdir()):
        if path.is_file() and not path.name.startswith("test_"):
            probes.append(f"scripts/{path.name}")
    lib = repo / "home/exact_lib"
    if lib.is_dir():
        for child in sorted(lib.iterdir()):
            if child.name.startswith("exact_,"):
                probes.append(f"home/exact_lib/{child.name}/")
    return tuple(dict.fromkeys(probes))


def _discover_tests(repo: Path) -> list[Path]:
    if str(repo / "scripts") not in sys.path:
        sys.path.insert(0, str(repo / "scripts"))
    import test_runner

    return test_runner.discover_files()


def _child_env(env: dict[str, str] | None = None) -> dict[str, str]:
    child = os.environ.copy()
    child["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        child.update(env)
    return child


def _run_capture(argv: tuple[str, ...], *, cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    result = subprocess.run(argv, cwd=str(cwd), env=_child_env(env), capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def _run_parallel(jobs: list[CheckJob], *, cwd: Path) -> int:
    if not jobs:
        return 0

    for job in jobs:
        print("+ " + " ".join(job.argv), flush=True)

    results: list[tuple[int, str, str] | None] = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=min(len(jobs), os.cpu_count() or 4)) as pool:
        futures = {pool.submit(_run_capture, job.argv, cwd=cwd, env=job.env): index for index, job in enumerate(jobs)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    first_rc = 0
    for result in results:
        assert result is not None
        rc, stdout, stderr = result
        if stdout:
            sys.stdout.write(stdout)
        if stderr:
            sys.stderr.write(stderr)
        if rc and not first_rc:
            first_rc = rc
    return first_rc


def run_plan(repo: Path, plan: CheckPlan) -> int:
    print(f"check: {plan.mode} ({len(plan.changed)} changed path(s))", flush=True)
    if plan.mode == "affected" and not (plan.fmt_paths or plan.ruff_paths or plan.gates or plan.tests or plan.extra):
        print("nothing to check", flush=True)
        return 0

    jobs: list[CheckJob] = []
    if plan.mode == "full":
        jobs.append(CheckJob(name="fmt", argv=("bin/fmt", "--check")))
        jobs.append(
            CheckJob(name="ruff-imports", argv=("ruff", "check", "--select", "I", "scripts/", "home/exact_lib/"))
        )
    else:
        if plan.fmt_paths:
            jobs.append(CheckJob(name="fmt", argv=("bin/fmt", "--check", *plan.fmt_paths)))
        if plan.ruff_paths:
            jobs.append(CheckJob(name="ruff-imports", argv=("ruff", "check", "--select", "I", *plan.ruff_paths)))

    gate_by_name = {gate.name: gate for gate in GATES}
    for name in plan.gates:
        jobs.append(CheckJob(name=name, argv=gate_by_name[name].argv))

    if plan.tests:
        jobs.append(CheckJob(name="tests", argv=(sys.executable, "scripts/test_runner.py", *plan.tests)))

    extra_by_name = {item.name: item for item in EXTRA_TESTS}
    for name in plan.extra:
        extra = extra_by_name[name]
        jobs.append(CheckJob(name=name, argv=extra.argv, env=dict(extra.env)))
    return _run_parallel(jobs, cwd=repo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="human-only full suite; requires CHECK_FULL=1 (agents must not use this)",
    )
    parser.add_argument("--staged", action="store_true", help="limit affected paths to the index")
    parser.add_argument("--print-plan", action="store_true", help="print JSON plan and exit")
    args = parser.parse_args(argv)

    if args.full and not args.print_plan and os.environ.get(FULL_ALLOW_ENV) != "1":
        print(
            "check: refusing --full without CHECK_FULL=1 (human-only; agents must run make check)",
            file=sys.stderr,
        )
        return 2

    if args.full:
        changed: tuple[str, ...] = ()
        add_delete = False
    else:
        changed, add_delete = collect_changed(REPO, staged=args.staged)
    plan = plan_check(REPO, full=args.full, changed=changed, add_delete=add_delete)
    if args.print_plan:
        json.dump(plan.as_json(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    return run_plan(REPO, plan)


if __name__ == "__main__":
    raise SystemExit(main())
