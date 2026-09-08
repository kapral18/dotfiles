#!/usr/bin/env python3
"""Focused tests for agent instruction invariants."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _test_support  # noqa: F401  (puts scripts/ on sys.path)
import ai_models
from _test_support import REPO


def render_chezmoi_template(path, *, is_work):
    if shutil.which("chezmoi") is None:
        raise unittest.SkipTest("chezmoi is required to render templates")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml") as config:
        config.write(f"[data]\nisWork = {str(is_work).lower()}\n")
        config.flush()
        result = subprocess.run(
            ["chezmoi", "--source", str(REPO), "--config", config.name, "execute-template"],
            input=path.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            check=True,
            cwd=str(REPO),
        )
    return result.stdout


SKILLS_ROOT = "home/exact_dot_agents/exact_skills"
ROOT_MOVES_HEADING = "## Root moves"
ROOT_MOVES_LEAD = (
    "Only the active root/main session follows this section; "
    "a delegated leaf skips it and returns findings to its parent."
)

# A launch instruction is a launch verb applied to an agent-shaped object.
# `spawn`/`launch`/`dispatch`/`delegate`/`fan out` name a launch by themselves, so an agent-shaped
# object anywhere in the same line makes the line an order.
_LAUNCH_VERB = re.compile(
    r"(?i)\b(spawn(s|ed|ing)?|launch(es|ed|ing)?|dispatch(es|ed|ing)?"
    r"|delegate(s|d)?|delegating|fan[- ]?out|fans out)\b"
)
_LAUNCH_OBJECT = re.compile(
    r"(?i)(agent|lane|worker|subagent|verifier|auditor|evaluator|refuter|task tool|workpool|k-agent-)"
)
# `start`/`use`/`hand`/`run`/`invoke` are ordinary English ("run the focused tests", "Controller-run
# lanes are told not to repeat them"), so they only order a launch when a named agent mechanism is
# their own object: "Run k-agent-code-searcher", "Hand the diff to k-agent-reviewer",
# "Use the Task tool to start three subagents" or "Use `task` with this packet".
# A hyphen-attached form is a compound adjective
# ("user-invoked hand-off", "model-invoked call"), never an order.
_NAMED_AGENT_LAUNCH = re.compile(
    r"(?i)(?<![-\w])(start(s|ed|ing)?|use(s|d)?|using|hand(s|ed|ing)?|run(s|ning)?|ran"
    r"|invoke(s|d)?|invoking)\b"
    r"(?:\s+[\w`'\u2019./-]+){0,3}?\s+['\"`]?"
    r"(task tool|task(?=[`'\"])|subagents?|k-agent-[a-z-]+)\b"
)
# Verbs a prohibition can ban, enumerated or not: "never launch, invoke, or delegate", "does not run".
_BANNED_VERBS = (
    r"launch|launches|launching|spawn|spawns|spawning|invoke|invokes|invoking"
    r"|delegate|delegates|delegating|dispatch|dispatches|dispatching|create|creates"
    r"|run|runs|running|use|uses|using|start|starts|starting|hand|hands|handing"
)
# Clauses that carry a launch verb without ordering a launch. Each one is deleted from the line
# before the verb/object test runs, so a line that both describes and orders a launch still fails.
_DESCRIPTIVE_CLAUSES = (
    # A factual negation of authority, not an imperative. Match only the named action
    # so a following positive launch in the same line remains visible to the scanner.
    re.compile(r"(?i)\bnot an instruction to\s+(launch|spawn|dispatch|delegate)\b"),
    # A ban, enumerated or not: "never launch, invoke, or delegate to another agent",
    # "cannot spawn", "with zero further subagent launches".
    re.compile(
        r"(?i)\b(never|not|cannot|can(?:'|\u2019)t|do not|must not|no|zero|without)[-\s]\s*"
        r"(further\s+)?((?!to\b)[\w-]+\s+){0,2}"
        rf"({_BANNED_VERBS})"
        rf"(\s*,?\s*(or\s+)?({_BANNED_VERBS}))*\b"
    ),
    # A role applicability header, not an order: "Use for `k-agent-review-worker` profiles".
    re.compile(r"(?i)\buse(d)?\s+for\b"),
    # The launch belongs to somebody else: "launching more subagents is out of scope".
    re.compile(
        r"(?i)\b(launch(es|ing)?|spawn(s|ing)?|dispatch(es|ing)?|delegation)\b[^.;]*?"
        r"\b(is|are|stay|stays|remain|remains)\s+"
        r"(out of|forbidden|prohibited|root-only|the parent|its parent|the controller|the root)\b"
    ),
    # Past participle used as an adjective: "delegated review lane", "only launched lanes cost tokens".
    re.compile(
        r"(?i)\b(delegated|launched|spawned|dispatched)\s+((?!to\b)[\w`'\u2019-]+\s+){0,3}"
        r"(child|children|worker|workers|leaf|leaves|subagent|subagents|agent|agents"
        r"|task|tasks|lane|lanes|flow|role|context|execution)\b"
    ),
    # The parent is the actor, so the sentence hands work up rather than out:
    # "the root dispatches the `k-agent-smol` scribe path".
    re.compile(
        r"(?i)\b(the|its)\s+(root|parent|controller)(?:'s|\u2019s)?(\s+[\w-]+)?\s+"
        r"(launch(es)?|spawn(s)?|dispatch(es)?|delegate(s)?|fans out)\b"
    ),
    # A launch named as a point in time, not ordered: "before launching lanes".
    re.compile(
        r"(?i)\b(before|after|until|once|while|when|during)\s+((?!to\b)[\w`'\u2019./-]+\s+){0,3}"
        r"(launch|launches|launching|launched|spawn|spawns|spawning|spawned"
        r"|dispatch|dispatches|dispatching|dispatched)\b"
    ),
    # The SOP's own rule name, not an order to dispatch: "SOP §3.7 `research` dispatch gate".
    re.compile(r"(?i)\b(dispatch|launch)\s+gate\b"),
    # An OS process, not an agent: "the port listener belongs to the spawned Kibana's process tree".
    re.compile(
        r"(?i)\bspawn(s|ed|ing)?\s+((?!to\b)[\w'\u2019-]+\s+){0,2}"
        r"(process|processes|kibana|elasticsearch|node|server|shell|container|listener)\b"
    ),
)


def skill_entry(skill_dir: Path):
    return next(
        (skill_dir / name for name in ("readonly_SKILL.md", "SKILL.md") if (skill_dir / name).is_file()),
        None,
    )


def is_manual_only(skill_dir: Path) -> bool:
    """True when the tree is user-invoked only, so no model ever autoloads its launch text."""
    entry = skill_entry(skill_dir)
    if entry is None:
        return False
    text = entry.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    return "disable-model-invocation: true" in text.split("---", 2)[1]


def _orders_a_launch(text: str) -> bool:
    """True when `text` orders a launch, after deleting the clauses that only describe or ban one."""
    for clause in _DESCRIPTIVE_CLAUSES:
        text = clause.sub(" ", text)
    if _LAUNCH_VERB.search(text) and _LAUNCH_OBJECT.search(text):
        return True
    return bool(_NAMED_AGENT_LAUNCH.search(text))


def launch_instruction_rows(lines) -> list[tuple[int, str]]:
    """`(line number, matched text)` rows for launch instructions outside a `## Root moves` section.

    Every candidate line is tested alone and then joined with the next candidate line, so an
    instruction that wraps across two physical lines (`Launch` / `` `k-agent-reviewer` over this
    diff.``) is caught at the line the verb sits on.
    """
    candidates: list[tuple[int, str]] = []
    in_root_moves = False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            # `###` headings stay inside the section their `##` opened.
            in_root_moves = line.strip() == ROOT_MOVES_HEADING
            continue
        if in_root_moves or line.strip() == ROOT_MOVES_LEAD:
            continue
        candidates.append((number, line))
    rows: list[tuple[int, str]] = []
    for index, (number, line) in enumerate(candidates):
        if _orders_a_launch(line):
            rows.append((number, line.strip()))
            continue
        following = candidates[index + 1] if index + 1 < len(candidates) else None
        if following is None or following[0] != number + 1 or _orders_a_launch(following[1]):
            continue
        window = f"{line.strip()} {following[1].strip()}"
        if _orders_a_launch(window):
            rows.append((number, window))
    return rows


def root_moves_violations(root: Path) -> list[str]:
    """Launch instructions in model-invocable skill text that sit outside a `## Root moves` section.

    Returns `path:line - text` rows; empty means every launch instruction is root-gated.
    """
    skills_root = root / SKILLS_ROOT
    if not skills_root.is_dir():
        raise FileNotFoundError(f"no skills tree at {skills_root}")
    violations = []
    for path in sorted(skills_root.rglob("*.md")):
        if is_manual_only(skills_root / path.relative_to(skills_root).parts[0]):
            continue
        for number, text in launch_instruction_rows(path.read_text(encoding="utf-8").splitlines()):
            violations.append(f"{path.relative_to(root)}:{number} - {text}")
    return violations


class TestAgentSkillInvariants(unittest.TestCase):
    def test_cursor_global_plugin_should_render_complete_sop_without_owning_other_plugins(self):
        plugin = REPO / "home/dot_cursor/plugins/local/exact_k-sop"
        manifest = json.loads((plugin / "dot_cursor-plugin/readonly_plugin.json").read_text())
        self.assertEqual(manifest["name"], "k-sop")
        self.assertEqual(manifest["rules"], "./rules")
        for is_work in (False, True):
            with self.subTest(is_work=is_work):
                rendered = render_chezmoi_template(plugin / "rules/readonly_sop.md.tmpl", is_work=is_work)
                self.assertEqual(
                    rendered,
                    "---\nalwaysApply: true\n---\n" + (REPO / "home/readonly_AGENTS.md").read_text(),
                )
        self.assertFalse((REPO / "home/dot_cursor/exact_plugins").exists())
        self.assertFalse((REPO / "home/dot_cursor/plugins/exact_local").exists())

    def assert_file_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"{relative_path} is missing instruction: {snippet}"

    def assert_file_not_contains(self, relative_path: str, *snippets: str) -> None:
        text = (REPO / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet not in text, f"{relative_path} should not contain: {snippet}"

    def test_skill_namespace_uses_k_prefix(self):
        # Copilot CLI validates the frontmatter `name` (dir name as fallback) and silently
        # drops leading `,`/`_`/`.`/`-`; dir-keyed harnesses (Claude/opencode/pi) use the
        # directory name. The uniform `k-` namespace avoids native-skill collisions in both,
        # so every skill dir and its frontmatter name must carry it.
        skills_root = REPO / "home/exact_dot_agents/exact_skills"
        name_re = re.compile(r"^name: \"?(?P<name>[^\"\n]+)\"?$", re.MULTILINE)
        for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
            assert skill_dir.name.startswith("exact_k-"), f"skill dir missing k- namespace: {skill_dir.name}"
            expected = skill_dir.name.removeprefix("exact_")
            entry = next(
                (skill_dir / c for c in ("readonly_SKILL.md", "SKILL.md") if (skill_dir / c).is_file()),
                None,
            )
            if entry is None:
                # symlink_SKILL.md points at an externally owned file; the dir prefix is
                # all this repo controls (e.g. codesift-code-search).
                assert (skill_dir / "symlink_SKILL.md").is_file(), f"{skill_dir.name} has no SKILL entrypoint"
                continue
            match = name_re.search(entry.read_text(encoding="utf-8"))
            assert match, f"{entry} has no frontmatter name"
            assert match.group("name") == expected, f"{entry} frontmatter name {match.group('name')!r} != {expected!r}"

    def test_repo_authored_subagents_use_k_agent_namespace(self):
        native_names = {
            "Explore",
            "Plan",
            "best-of-n-runner",
            "browser_agent",
            "bugbot",
            "claude",
            "claude-code-guide",
            "cli_help",
            "code-review",
            "codebase_investigator",
            "cursor-guide",
            "default",
            "explore",
            "explorer",
            "general-purpose",
            "generalPurpose",
            "generalist",
            "rem-agent",
            "research",
            "reviewer",
            "rubber-duck",
            "scout",
            "security-review",
            "security-reviewer",
            "sonic",
            "task",
            "worker",
        }
        profile_roots = (
            REPO / "home/dot_claude/exact_agents",
            REPO / "home/dot_codex/exact_agents",
            REPO / "home/dot_cursor/exact_agents",
            REPO / "home/dot_omp/private_agent/exact_agents",
            REPO / "home/dot_pi/agent/exact_agents",
            REPO / "home/private_dot_copilot/exact_agents",
        )
        name_re = re.compile(r'^name(?:\s*=|:)\s*"?(?P<name>[^"\n]+)"?$', re.MULTILINE)
        profile_names: dict[str, set[str]] = {}

        for root in profile_roots:
            names: set[str] = set()
            for profile in sorted(path for path in root.iterdir() if path.name.endswith(".tmpl")):
                match = name_re.search(profile.read_text(encoding="utf-8"))
                assert match, f"{profile} has no frontmatter name"
                name = match.group("name")
                names.add(name)
                if name not in native_names:
                    assert name.startswith("k-agent-"), f"repo-authored subagent lacks k-agent- prefix: {name}"

                source_name = profile.name.removeprefix("readonly_")
                for suffix in (".agent.md.tmpl", ".toml.tmpl", ".md.tmpl"):
                    source_name = source_name.removesuffix(suffix)
                assert source_name == name, f"{profile} filename does not match its agent name {name!r}"
            profile_names[str(root.relative_to(REPO))] = names

        claude_native_profiles = {"Explore", "Plan", "claude", "claude-code-guide", "general-purpose"}
        assert claude_native_profiles <= profile_names["home/dot_claude/exact_agents"]

        bindings = ai_models.load_agent_bindings(REPO / "home/.chezmoidata/ai_models")
        assert native_names <= set(bindings), "native subagent bindings must keep their harness identifiers"
        # A native identifier must not gain a `k-agent-` twin: two bindings for one harness profile
        # is exactly the drift this guards. `reviewer` is declared — OMP's built-in name happens to
        # be the suffix of the long-standing repo-authored `k-agent-reviewer` review lane, which is
        # a different agent, not an alias of it.
        declared_suffix_collisions = {"k-agent-reviewer"}
        native_aliases = {f"k-agent-{name}" for name in native_names} - declared_suffix_collisions
        offenders = sorted(native_aliases & set(bindings))
        assert not offenders, f"native subagent identifiers must not gain k-agent aliases: {offenders}"

    def test_category_bindings_and_profile_presence_match_the_dispatch_targets(self):
        # SOP §3.7 names a concrete dispatch target per category, and two things must line up for a
        # launch to land on the right band: the registry binding, which prices the lane, and a
        # profile the harness can actually reach by name. A binding with no profile means the
        # controller falls back to a generic type on the implement band; a profile with no binding
        # resolves to whatever the caller asked for. Both failures are silent.
        expected_bindings = {
            # Repo-authored lanes the §3.7 gates name by hand.
            "k-agent-public-sources": "research",
            "k-agent-mechanical": "mechanical",
            "k-agent-implementer": "implement",
            "k-agent-claim-verifier": "refute",
            # OMP built-ins (the omp task-tool roster): `sonic` applies settled edits and `scout`
            # does read-only exact retrieval, both T3 mechanical; `reviewer`/`security-reviewer`
            # are T1 review; `task` is the T2 implement worker the implement gate names.
            "sonic": "mechanical",
            "scout": "mechanical",
            "reviewer": "review",
            "security-reviewer": "review",
            "task": "implement",
        }
        bindings = ai_models.load_agent_bindings(REPO / "home/.chezmoidata/ai_models")
        for agent, category in expected_bindings.items():
            with self.subTest(agent=agent):
                self.assertEqual(category, bindings.get(agent))

        agents_dirs = {
            "claude": REPO / "home/dot_claude/exact_agents",
            "codex": REPO / "home/dot_codex/exact_agents",
            "copilot": REPO / "home/private_dot_copilot/exact_agents",
            "cursor": REPO / "home/dot_cursor/exact_agents",
            "omp": REPO / "home/dot_omp/private_agent/exact_agents",
            "pi": REPO / "home/dot_pi/agent/exact_agents",
        }
        profiles: dict[str, set[str]] = {}
        for harness, root in agents_dirs.items():
            names = set()
            for entry in root.glob("*.tmpl"):
                name = entry.name.removeprefix("readonly_")
                for suffix in (".agent.md.tmpl", ".toml.tmpl", ".md.tmpl"):
                    name = name.removesuffix(suffix)
                names.add(name)
            assert names, f"{root} has no agent profiles"
            profiles[harness] = names

        everywhere = set(agents_dirs)
        # The three harnesses that run the full review controller: OMP and Pi carry the whole lane
        # set, and Claude gained the verifier profiles with the same retier.
        controller_harnesses = {"claude", "omp", "pi"}
        # (required, forbidden) per agent; `forbidden` is only used where the profile is deliberately
        # exclusive, so a harness gaining an unlisted verifier profile is not a failure.
        expected_presence = {
            # The one lane every harness must reach by name: the mechanical gate has no generic
            # fallback that keeps the band on the cheap tier.
            "k-agent-mechanical": (everywhere, set()),
            # Pi-only: Pi disables built-in subagents and exposes no generic edit-capable type, so a
            # named profile is the only reachable T2 target there (tiering.yaml k-agent-implementer).
            "k-agent-implementer": ({"pi"}, everywhere - {"pi"}),
            "k-agent-claim-verifier": (controller_harnesses, set()),
            "k-agent-fresh-eyes": (controller_harnesses, set()),
            "k-agent-adversarial-verifier": (controller_harnesses, set()),
            "k-agent-criteria-verifier": (controller_harnesses, set()),
        }
        for agent, (required, forbidden) in expected_presence.items():
            for harness in sorted(required):
                with self.subTest(agent=agent, harness=harness, presence="required"):
                    self.assertIn(agent, profiles[harness])
            for harness in sorted(forbidden):
                with self.subTest(agent=agent, harness=harness, presence="forbidden"):
                    self.assertNotIn(agent, profiles[harness])

    def test_skill_description_with_colon_is_quoted(self):
        skills_root = REPO / "home/exact_dot_agents/exact_skills"
        description_re = re.compile(r"^description:\s+(?P<value>[^\"'\n].*:.*)$", re.MULTILINE)
        for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
            entry = next(
                (skill_dir / c for c in ("readonly_SKILL.md", "SKILL.md") if (skill_dir / c).is_file()),
                None,
            )
            if entry is None:
                continue
            match = description_re.search(entry.read_text(encoding="utf-8"))
            assert not match, f"{entry} has an unquoted description containing ':': {match.group('value')}"

    def test_pi_named_dispatch_targets_have_profiles(self):
        # Pi disables built-in subagents and exposes no generic edit-capable type, so every lane the
        # SOP dispatches has to exist here as a named profile — there is no fallback that keeps the
        # band. Former controller profiles are leaves and MUST NOT carry a launch roster.
        agents_dir = REPO / "home/dot_pi/agent/exact_agents"
        profiles = {path.name.removesuffix(".md.tmpl") for path in agents_dir.glob("*.md.tmpl")}
        controller = (agents_dir / "k-agent-review-controller.md.tmpl").read_text(encoding="utf-8")
        optional_final_roles = {
            "k-agent-reviewer",
            "k-agent-fresh-eyes",
            "k-agent-adversarial-verifier",
            "k-agent-pr-necessity-auditor",
            "k-agent-live-ui-review",
            "k-agent-findings-auditor",
        }
        # k-agent-implementer is the Pi-only T2 implement target and k-agent-claim-verifier the
        # public-claim refuter; neither is a review-controller lane, so they are pinned for
        # existence only.
        required = optional_final_roles | {"k-agent-implementer", "k-agent-claim-verifier"}

        assert required <= profiles, f"Pi is missing dispatch-target profiles: {sorted(required - profiles)}"
        assert "leaf-boundary.txt" in controller
        assert "reviewer-worker.md" in controller
        assert "  - k-deep-review" not in controller
        assert "  - k-review" not in controller

    def test_pi_settings_use_native_shared_skills_and_real_extension_packages(self):
        for profile in ("work", "personal"):
            path = REPO / f"home/dot_pi/agent/readonly_settings.{profile}.json"
            settings = json.loads(path.read_text(encoding="utf-8"))
            assert settings["packages"] == [
                "~/.local/share/yarn/global/node_modules/pi-mcp-adapter",
                "~/.local/share/yarn/global/node_modules/pi-subagents",
            ]

    def test_pi_extensions_directory_prunes_unmanaged_drops(self):
        # Pi auto-loads every entry under ~/.pi/agent/extensions and aborts the whole session
        # when one fails to import. A hand-dropped pi-subagents clone with no node_modules did
        # exactly that ("Cannot find module 'yaml'") while the yarn package in `packages` was
        # fine. `exact_` is the guard: chezmoi apply deletes anything not in the source tree.
        managed = REPO / "home/dot_pi/agent/exact_extensions"
        assert managed.is_dir(), (
            "home/dot_pi/agent/exact_extensions must keep the exact_ prefix so chezmoi prunes "
            "unmanaged extension drops instead of letting them break every Pi session"
        )
        assert not (REPO / "home/dot_pi/agent/extensions").exists(), (
            "a non-exact home/dot_pi/agent/extensions directory would stop pruning again"
        )

    def test_convergence_is_explicit_finite_and_never_hook_started(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-converge/readonly_SKILL.md",
            "disable-model-invocation: true",
            "finite",
        )
        for impl in (
            "home/exact_dot_agents/exact_hooks/executable_perturn_recall.py",
            "home/dot_pi/agent/exact_extensions/ai-kb-recall.ts",
            "home/dot_omp/private_agent/extensions/ai-kb-recall.ts",
        ):
            self.assert_file_contains(impl, "Do not launch re-verification, convergence, or a memory agent")
            self.assert_file_not_contains(
                impl, "delegate persistence to", "re-verify it against the artifact", "/k-converge"
            )

    def test_every_wired_hook_command_has_a_chezmoi_source_file(self):
        # A harness config can name `$HOME/.agents/hooks/<x>.py` for a file that was never
        # written: the config parses, the census counts drift, and the hook silently no-ops or
        # errors per harness at runtime. Nothing else in the suite ties the reference to the file,
        # so this walks every config that wires hooks and resolves each command back to its
        # chezmoi source (`exact_hooks/<x>` deploys as `~/.agents/hooks/<x>`, minus the
        # `executable_`/`readonly_` attribute prefixes).
        hooks_dir = REPO / "home/exact_dot_agents/exact_hooks"
        available = set()
        for entry in hooks_dir.iterdir():
            name = entry.name
            for prefix in ("executable_", "readonly_", "private_"):
                name = name.removeprefix(prefix)
            available.add(name.removesuffix(".tmpl"))

        configs = (
            "home/dot_claude/settings.personal.json",
            "home/dot_claude/settings.work.json",
            "home/dot_claude/settings.llama-cpp.json.tmpl",
            "home/dot_claude/settings.llama-cpp.qwen3.8.json.tmpl",
            "home/dot_codex/hooks.json.tmpl",
            "home/dot_cursor/hooks.json",
            "home/dot_gemini/config/readonly_hooks.json",
        )
        referenced = re.compile(r"\.agents/hooks/([A-Za-z0-9_.-]+\.(?:py|sh))")
        checked = 0
        for config in configs:
            text = (REPO / config).read_text(encoding="utf-8")
            for name in referenced.findall(text):
                checked += 1
                assert name in available, f"{config} wires ~/.agents/hooks/{name}, which has no source in {hooks_dir}"
        assert checked, "no hook references found; the regex or the config list is stale"

    def test_claude_llama_cpp_settings_disable_attribution_header(self):
        settings = json.loads(
            render_chezmoi_template(REPO / "home/dot_claude/settings.llama-cpp.json.tmpl", is_work=True)
        )
        self.assertEqual(settings["env"]["CLAUDE_CODE_ATTRIBUTION_HEADER"], "0")
        self.assertEqual(settings["autoCompactWindow"], 200000)
        qwen38_settings = json.loads(
            render_chezmoi_template(REPO / "home/dot_claude/settings.llama-cpp.qwen3.8.json.tmpl", is_work=True)
        )
        self.assertEqual(qwen38_settings["env"]["CLAUDE_CODE_ATTRIBUTION_HEADER"], "0")
        self.assertEqual(qwen38_settings["autoCompactWindow"], 100000)

        personal_settings = json.loads(
            render_chezmoi_template(REPO / "home/dot_claude/settings.llama-cpp.json.tmpl", is_work=False)
        )
        self.assertEqual(personal_settings["autoCompactWindow"], 200000)
        qwen38_personal_settings = json.loads(
            render_chezmoi_template(REPO / "home/dot_claude/settings.llama-cpp.qwen3.8.json.tmpl", is_work=False)
        )
        self.assertEqual(qwen38_personal_settings["autoCompactWindow"], 200000)

    def test_ai_docs_track_current_runtime_contracts(self):
        self.assert_file_contains(
            "docs/topics/ai-assistants/tool-configs/other-harnesses.md",
            "injects a bearer token minted by cursor-cli per request",
            "`,copilot` passes through to the real binary except for bare `--resume`",
            "The bearer-free `~/.copilot/mcp-config.json`",
        )
        self.assert_file_not_contains(
            "docs/topics/ai-assistants/tool-configs/other-harnesses.md",
            "Before launch, `,copilot` holds a private config lock",
            "sends the Authorization values to a single generator render over stdin",
            "The token-bearing `~/.copilot/mcp-config.json`",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/tool-configs/profile-merging.md",
            "Copilot MCP rendering is apply-time only",
            "Runtime `,copilot` does not render config or change the ledger",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/llama-cpp/launchers.md",
            "Hosted MCP authentication is owned by the per-request stdio bridges",
            "CLAUDE_CODE_ATTRIBUTION_HEADER",
        )
        self.assert_file_not_contains(
            "docs/topics/ai-assistants/llama-cpp/launchers.md",
            "refreshes any configured Codex hosted-MCP bearer-token env vars",
            "after the MCP env-var setup",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/mcp.md",
            "emitted to every work-profile harness, including OMP, Copilot, and Codex",
            "OpenCode gets `scsi-local` only",
            "HTTP entries are intentionally skipped",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/tool-configs/claude-gemini.md",
            "`alwaysThinkingEnabled: false`; `effortLevel: xhigh`",
        )
        self.assert_file_not_contains(
            "docs/topics/ai-assistants/scenarios.md",
            "`/improve-…`",
            "**anything → compose-issue.**",
        )
        self.assert_file_contains(
            "home/readonly_CLAUDE.md",
            "@AGENTS.md",
        )
        self.assert_file_contains(
            "home/dot_claude/symlink_CLAUDE.md",
            "../AGENTS.md",
        )
        self.assert_file_not_contains(
            ".mermaids/03-agentic-os.mmd",
            "readonly_GEMINI.md",
        )
        self.assert_file_not_contains(
            ".mermaids/11-scripts-helpers.mmd",
            "Copilot typed header-auth plan + stdin override render",
        )
        self.assert_file_not_contains(
            ".mermaids/SR-index.mmd",
            "re-apply hook 06",
            "source: readonly_*",
            "keep 3 entrypoints in sync",
        )

    def test_workflow_recipes_share_the_terminal_verify_stage(self):
        for name in ("k-build", "k-deep-review", "k-light-review"):
            path = f"home/exact_dot_agents/exact_skills/exact_{name}/readonly_SKILL.md"
            self.assert_file_contains(path, "Verify")
            self.assert_file_not_contains(
                path,
                "Repeat until no findings remain",
                "repeat until no findings remain",
                "switch to `~/.agents/skills/k-converge/SKILL.md`",
            )

    def test_github_pr_publication_requires_preflight_and_readback_comparison(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "PR creation is a composition action; it is not exempt.",
            "Load `~/.agents/skills/k-github/references/pr-create.md`",
            'Approval to "create a PR" authorizes the GitHub side effect, but not invented human-visible content.',
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-create.md",
            "Before the side effect, show:",
            "Compare each field against the approved preflight ledger",
        )

    def test_issue_publication_requires_type_packet(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-issue/readonly_SKILL.md",
            "issue title/body draft or issue publication packet",
            "issue publication packet",
            "`issue_type`: exact GitHub issue type",
            "labels do not satisfy it",
            "pick from the repo's actual issue types",
            "Return the issue title/body draft and the issue publication packet",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "Load `~/.agents/skills/k-github/references/issue-create.md`",
            "issue type gate",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_issue-create.md",
            "Before `gh issue create`",
            "`k-compose-issue` issue publication packet",
            "gh issue create --type <IssueType>",
            "do not silently fall back to labels-only creation",
            "issue type via GraphQL",
        )

    def test_compose_pr_preserves_context_and_test_plan_gates(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/readonly_SKILL.md",
            "PR title/body or publication packet",
            "Load `~/.agents/skills/k-compose-pr/references/publication-packet.md`",
            "Treat changed paths as scope clues only",
            "Verify each proposed Test Plan command or manual step",
            "PR publication packet",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/exact_references/readonly_publication-packet.md",
            "The gate is not complete from previews or sliced fields",
            "PR Test Plan completeness gate",
            "Test Plan must be evidence: runnable command or manual step, expected result, and observed result.",
            "Before proposing a Test Plan command or manual step",
            "do not present it as runnable Test Plan evidence",
            "Test Plan MUST NOT mirror or enumerate changed test paths",
            "part of a command or concrete repro step",
            "Manual Test Plan steps must be reader-executable",
            "Do not combine setup, choice, and verification in one sentence.",
            "run the false-positive check",
            "Preserve required setup state",
            "when that state makes the old bug observable",
            "manual-only, keep executed commands and observed local validation",
            "include the expected observable result after the fix",
            "pending_approval",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-compose-pr/exact_references/readonly_publication-packet.md",
            "Test Plan must be evidence: commands run + observed result.",
        )

    def test_kibana_domain_owns_pr_title_and_metadata_boundaries(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/readonly_SKILL.md",
            "Before preparing that text or its domain metadata, read and follow `~/.agents/skills/k-elastic-domain/references/github-composition.md` in full.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/exact_references/readonly_github-composition.md",
            "generic skills must not invent fallback Kibana title style, labels, release-note state, or footer policy",
            "PR titles should use Kibana's bracketed area style",
            "Do not use a Conventional Commit header as the PR title unless that exact area has precedent",
        )

    def test_kibana_label_guidance_blocks_esql_label_from_console_mentions(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kibana-labels-propose/readonly_SKILL.md",
            "this skill is the source of truth for `elastic/kibana` label/backport/version classification",
            "when all changed paths and the linked issue point to Console, propose `Feature:Console`",
            "do not add `Feature:ES|QL` unless there is separate evidence",
            "pending_approval",
        )

    def test_git_commit_style_does_not_control_pr_titles(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-git/readonly_SKILL.md",
            "Before composing a commit message or running commit, amend, or push commands, MUST load and follow `~/.agents/skills/k-git/references/commit-push.md`.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-git/exact_references/readonly_commit-push.md",
            "commit-message style does not transfer to PR titles",
            "PR titles are owned by `k-github` plus any verified domain overlay",
        )

    def test_github_skill_extracts_pr_review_and_sub_issue_references(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "`~/.agents/skills/k-github/references/pr-reviews.md`",
            "`~/.agents/skills/k-github/references/pr-comments.md`",
            "`~/.agents/skills/k-github/references/sub-issues.md`",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/readonly_SKILL.md",
            "Add a soft close such as `Wdyt`",
            "Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`",
            "Practical constraint: GitHub generally allows only one",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-reviews.md",
            "NEVER include `event` in the create-review payload",
            "Practical constraint: GitHub generally allows only one `PENDING` review per user per PR",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-comments.md",
            "Add a soft close such as `Wdyt` only when the review style calls for it",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_sub-issues.md",
            "Mutations: `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`",
        )

    def test_pr_review_submission_uses_short_summary_and_team_aware_verdict(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_authorship.md",
            "`author_relation`",
            "For `authorship: other` or `unknown`",
            "`immediate_team`: verified from a loaded domain overlay",
            "`outside_or_unknown_team`: any author not verified as immediate team",
            "Do not infer immediate-team membership",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_shared_rules.md",
            "Before drafting review comments/replies/descriptions or recommending a PR verdict, load `~/.agents/skills/k-review/references/review_delivery.md`.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_delivery.md",
            """**Self-review** (`authorship: self`):
  - Review alone does not authorize edits. Report remaining findings; repairs after final Verify require a new user-authorized attempt.
  - **Comment only** if the user explicitly asks to post self-review notes with remaining non-blocking findings.
  - **Approve** when no findings remain.
  - Do not request changes on the user's own PR from this flow.""",
            """**Immediate-team author**:
  - **Request changes** only for a CRITICAL blocker that must be addressed before merge.
  - **Comment only** when findings remain below CRITICAL. Trust teammates to judge whether comment-level feedback should block.
  - **Approve** when no findings remain.""",
            """**Outside or unknown-team author**:
  - **Request changes** for CRITICAL or HIGH findings that must be addressed before merge.
  - **Comment only** for MEDIUM findings.
  - **Approve with comments** for LOW findings or true nits.
  - **Approve** when no findings remain.""",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_review.md",
            "keep the body as a short acknowledgement",
            "`Looks good.` for a clean approval",
            "`Left inline feedback.` when comments exist",
            "Do not repeat, summarize, or enumerate details that are already in inline comments",
            "Use it only when a PR-level comment is explicitly needed, and never to repeat inline-comment content",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-reviews.md",
            "The body is a short acknowledgement, not a second review",
            "Do not copy inline-comment details into the submit body",
            "Keep the draft pending-review body empty unless the user explicitly wants a non-empty draft body to submit later",
            "The submitted review body should stay short and sweet",
            "For a clean approval, use an acknowledgement that does not claim inline comments exist",
            "acknowledge the review outcome",
            "do not repeat, summarize, or enumerate their details",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-reviews.md",
            "Keep the pending review summary body empty; fill it only when the user explicitly wants a public summary.",
            "public summary",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-communication/readonly_SKILL.md",
            "PR review submit bodies are acknowledgements, not summaries",
            "Do not repeat, summarize, or enumerate details already present in inline comments",
            "PR review summary bodies are short acknowledgements",
            "`Looks good.` for clean approvals",
            "`Left inline feedback.` when comments exist",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/reviews/replies-publication-and-history.md",
            "Review submit summary bodies are short acknowledgements",
            "Do not repeat details already present in inline comments",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/skills/review-and-delivery.md",
            "Review submit bodies stay short: acknowledge the review outcome",
            "when inline comments exist, do not repeat their details",
            "For immediate-team PR authors, clean reviews approve, findings below CRITICAL use comment review, and CRITICAL blockers request changes; outside or unknown-team authors use the normal severity ladder.",
        )
        for relative_path in (
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_review.md",
            "home/exact_dot_agents/exact_skills/exact_k-github/exact_references/readonly_pr-reviews.md",
            "home/exact_dot_agents/exact_skills/exact_k-communication/readonly_SKILL.md",
            "docs/topics/ai-assistants/reviews/replies-publication-and-history.md",
            "docs/topics/ai-assistants/skills/review-and-delivery.md",
        ):
            self.assert_file_not_contains(
                relative_path,
                "Left a few inline comments",
                "Left a few comments inline",
                "Left inline comments on <topics>",
                "PR review summary bodies describe inline topics, not commands",
                "acknowledge that comments were left inline",
                "public draft body",
            )
        for relative_path in (
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_shared_rules.md",
            "docs/topics/ai-assistants/reviews/replies-publication-and-history.md",
            "docs/topics/ai-assistants/skills/review-and-delivery.md",
        ):
            self.assert_file_not_contains(
                relative_path,
                "**Approve**: no CRITICAL/HIGH findings remain; all findings are LOW/MEDIUM nits or suggestions.",
                "**Request changes**: at least one CRITICAL or HIGH finding that must be addressed before merge.",
                "**Comment only**: findings exist but are informational/advisory; merge is not blocked.",
            )

    def test_review_router_dirty_pr_docs_match_source(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md",
            "If both are true: default to local changes mode (review the working tree; do not infer fix authority).",
            "Note the PR exists in output so the user can switch if needed.",
        )
        self.assert_file_contains(
            "docs/topics/ai-assistants/reviews/replies-publication-and-history.md",
            "When both a dirty working tree and a current-branch PR exist, the router defaults to local changes mode",
            "notes that the PR exists so the user can switch if needed",
            "SOP `3.8` in the single source",
        )
        self.assert_file_not_contains(
            "docs/topics/ai-assistants/reviews/replies-publication-and-history.md",
            "the router asks which target to review instead of silently forcing local review first",
            "SOP `3.6` in the single source",
        )

    def test_elastic_domain_skill_extracts_pr_issue_templates_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/readonly_SKILL.md",
            "Before preparing that text or its domain metadata, read and follow `~/.agents/skills/k-elastic-domain/references/github-composition.md` in full.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/exact_references/readonly_github-composition.md",
            "`~/.agents/skills/k-elastic-domain/references/pr-issue-templates.md`",
            "include environment details when UI or deployment matters",
            "leave unknown stack/deployment/browser fields blank or marked for follow-up; do not invent them",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/readonly_SKILL.md",
            "## PR template: Bugfix",
            "## Issue template: Kibana",
            "Single sentence describing the user-facing behavior change.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-elastic-domain/exact_references/readonly_pr-issue-templates.md",
            "## PR template: Bugfix",
            "## Issue template: Kibana",
            "Single sentence describing the user-facing behavior change.",
        )

    def test_kbn_backport_skill_extracts_conflict_resolution_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kbn-backport/readonly_SKILL.md",
            "`~/.agents/skills/k-kbn-backport/references/conflict-resolution.md`",
            "Triggered only when the run pauses with a conflict on the current target branch.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kbn-backport/readonly_SKILL.md",
            "When the run pauses on a conflict, MUST load and follow Stage And Continue The Run in `~/.agents/skills/k-kbn-backport/references/conflict-resolution.md` before sending ENTER.",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kbn-backport/exact_references/readonly_conflict-resolution.md",
            "Apply The Resolution, in `references/conflict-resolution.md`",
            "Validation (`references/conflict-resolution.md`) so the verifiers actually run and pass",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kbn-backport/readonly_SKILL.md",
            "## Understand The Original Change",
            "## Resolution Rules",
            "node scripts/jest --config=",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-kbn-backport/exact_references/readonly_conflict-resolution.md",
            "## Understand The Original Change",
            "## Resolution Rules",
            "node scripts/jest --config=<package>/jest.config.js <test-file>",
        )

    def test_letsfg_skill_extracts_flexible_date_search_reference(self):
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-letsfg/readonly_SKILL.md",
            "`~/.agents/skills/k-letsfg/references/flexible-date-search.md`",
        )
        self.assert_file_not_contains(
            "home/exact_dot_agents/exact_skills/exact_k-letsfg/readonly_SKILL.md",
            "from concurrent.futures import ThreadPoolExecutor",
            "ThreadPoolExecutor(max_workers=min(2, len(dates)))",
        )
        self.assert_file_contains(
            "home/exact_dot_agents/exact_skills/exact_k-letsfg/exact_references/readonly_flexible-date-search.md",
            "from concurrent.futures import ThreadPoolExecutor",
            "ThreadPoolExecutor(max_workers=min(2, len(dates)))",
        )

    def test_root_moves_sections_present(self):
        # SOP §3.7 makes launch/fan-out text root-only, and a leaf cannot honor that per sentence:
        # it needs one skippable section. Every model-invocable skill that still carries launch text
        # declares it, so the child profiles that preload these files have a boundary to skip.
        for skill in (
            "exact_k-ai-kb",
            "exact_k-codebase-design",
            "exact_k-light-review",
            "exact_k-omp",
            "exact_k-review",
            "exact_k-spec",
            "exact_k-text-tournament",
        ):
            path = REPO / SKILLS_ROOT / skill / "readonly_SKILL.md"
            lines = path.read_text(encoding="utf-8").splitlines()
            assert ROOT_MOVES_HEADING in lines, f"{path} has no `{ROOT_MOVES_HEADING}` section"

    def test_root_moves_guard_dispatch_text(self):
        # The boundary is only real if it is both announced and complete: a leaf must be able to
        # recognize the section from its first line, and no launch instruction may sit outside one.
        unannounced = []
        for path in sorted((REPO / SKILLS_ROOT).rglob("*.md")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if line.strip() != ROOT_MOVES_HEADING:
                    continue
                body = [text.strip() for text in lines[index + 1 :] if text.strip()]
                if not body or body[0] != ROOT_MOVES_LEAD:
                    unannounced.append(f"{path.relative_to(REPO)}:{index + 1}")
        assert not unannounced, (
            "every `## Root moves` section must open with the leaf-skip sentence, missing in: " + ", ".join(unannounced)
        )

        violations = root_moves_violations(REPO)
        assert not violations, "launch instructions outside a `## Root moves` section:\n" + "\n".join(violations)

    def test_root_moves_scanner_catches_counterexamples(self):
        # Adversarial grammar from `agent://CriteriaVerifier`: moving words around must not make the
        # invariant green while the launch order survives. Each row is a scanned body plus whether
        # it orders a launch; `False` rows are the exemptions the real contracts depend on.
        probes = (
            (False, "A staged pointer is not an instruction to launch an agent."),
            (True, "A staged pointer is not an instruction to launch an agent; spawn k-agent-reviewer now."),
            # Weak verbs and a wrapped object — the five orders the first vocabulary missed.
            (True, "Use the Task tool to start three subagents."),
            (True, "Use `task` and `hub` for typed agent work and process lifecycle."),
            (True, "Run the native `task` with a ready packet."),
            (False, "Use the task state to resume."),
            (False, "Run the task tests."),
            (False, "Do not use `task` from a leaf."),
            (True, "Hand the diff to k-agent-reviewer."),
            (True, "Run k-agent-code-searcher over the tree."),
            (True, "Invoke k-agent-reviewer to inspect the diff."),
            (True, "Launch\n`k-agent-reviewer` over this diff."),
            # A prohibition or a parent-as-actor description next to a real order stays caught.
            (True, "Do not launch other agents; spawn k-agent-reviewer for this diff."),
            (True, "The parent dispatches a research lane; launch k-agent-reviewer now."),
            (True, "Spawn k-agent-reviewer to audit the diff."),
            # Real contract sentences: a leaf's no-spawn sentence, a ban, the parent as actor,
            # a launch named as a point in time, and ordinary English uses of the weak verbs.
            (
                False,
                "- You run as a delegated leaf worker: never launch, invoke, or delegate to another"
                " agent; return findings to the parent.",
            ),
            (
                False,
                "A delegated leaf other than the `k-agent-smol` operator does not run recall or"
                " persistence; it returns candidate insights to its parent.",
            ),
            (
                False,
                "You run in an isolated context as a leaf worker: you cannot spawn agents, so never"
                " attempt the independent verification yourself — the parent dispatches that separately.",
            ),
            (False, "Those are shared work: the controller runs them once and passes the result to every lane."),
            (False, "Before launching any lane, re-read `<topic>.txt`."),
            (
                False,
                "Controller-run lanes receive distilled base context from the controller, which owns"
                " the dispatched `k-agent-code-searcher` research lane.",
            ),
            # Joining two lines must catch a wrapped order without inventing one.
            (
                False,
                "Run the focused tests and lint for the touched files.\n"
                "The `k-agent-implementer` packet names the check to run.",
            ),
        )
        for expected, body in probes:
            rows = launch_instruction_rows(body.splitlines())
            label = "missed launch instruction" if expected else "false positive"
            assert bool(rows) == expected, f"{label}: {body!r} -> {rows}"

        # The section is what makes a caught row actionable: the same order inside `## Root moves`
        # is root-only text the leaf skips, not a violation.
        gated = [ROOT_MOVES_HEADING, "", ROOT_MOVES_LEAD, "", "- Spawn k-agent-reviewer to audit the diff."]
        assert not launch_instruction_rows(gated), "a `## Root moves` order must stay exempt"
