#!/usr/bin/env python3
"""Regression tests for user-correction mistake-capture hook injection."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

import _test_support  # noqa: F401
from _test_support import REPO

HOOKS = REPO / "home" / "exact_dot_agents" / "exact_hooks"
DETECTOR = HOOKS / "correction_detector.py"


def _load_detector():
    loader = SourceFileLoader("correction_detector_test", str(DETECTOR))
    spec = importlib.util.spec_from_loader("correction_detector_test", loader)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load correction detector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _deploy_hooks(root: Path) -> Path:
    deployed = root / "deployed-hooks"
    deployed.mkdir(parents=True)
    for source, target in (
        ("hook_common.py", "hook_common.py"),
        ("executable_session_context.py", "session_context.py"),
        ("executable_perturn_recall.py", "perturn_recall.py"),
        ("correction_detector.py", "correction_detector.py"),
    ):
        (deployed / target).write_text((HOOKS / source).read_text(encoding="utf-8"), encoding="utf-8")
    return deployed


correction_detector = _load_detector()


STRONG_CORRECTIONS = [
    (
        "I didn't ask you to commit so why the fuck you did it? never commit, I soft resetted…",
        "unrequested-action",
    ),
    (
        "ok  Isee. about the 20s later thing, did you really measure it or was it a hallucination of yours?",
        "unverified-claim",
    ),
    (
        "you last comment advocates for dropping aria-label are you sure have you tried that that's the cure or you guessed?",
        "guessed-not-tested",
    ),
    (
        "so instead of testing you want to demote it? where is the search for truth?",
        "guessed-not-tested",
    ),
    ("then why did you not include the link to that thread", "omission-correction"),
    ("this is still wrong", "repeat-failure"),
    ("never push directly again", "unrequested-action"),
    ("it's still broken after your fix", "repeat-failure"),
]

NEUTRAL_PROMPTS = [
    "/k-agent-review https://github.com/elastic/kibana/pull/277247",
    "submit as pending review and tell me where to add each image",
    "there should be a way to drag and drop images in, there has to be via playwriter i cna't believe there isnt",
    "listen there should be a way maybe we should first find a way to upload the images to get the links…",
    "ok this deserves a separate skill in chezmoi? how about we create one or integrate in existing one?…",
    "but upload of images/videos is a generic mechanism it can happen from any flow…",
    "done try again",
    "ok submit as a comment",
    "wdyt? maybe you should recapture the images properly?",
    "why did you choose sqlite here?",
    "are you sure?",
    "why is the popup semi-transparent",
    "can you check why the test is failing",
    "why did you decide to stop supporting python 2?",
    "why did you use a dict instead of a list? I don't have a strong preference, just curious",
]


class TestCorrectionDetector(unittest.TestCase):
    def test_when_prompt_is_strong_user_correction_should_return_expected_signal(self):
        for prompt, signal in STRONG_CORRECTIONS:
            with self.subTest(prompt=prompt):
                self.assertEqual(correction_detector.detect(prompt), signal)

    def test_when_prompt_is_neutral_or_product_defect_should_not_fire(self):
        for prompt in NEUTRAL_PROMPTS:
            with self.subTest(prompt=prompt):
                self.assertIsNone(correction_detector.detect(prompt))

    def test_when_prompt_is_too_short_should_not_fire(self):
        self.assertIsNone(correction_detector.detect("wrong"))

    def test_when_prompt_is_huge_pasted_text_should_stay_fast_and_bounded(self):
        # Regression: the pre-cap detector took >130s on a ~1.1MB prompt with an
        # "are you sure" prefix and scattered standalone "or" tokens.
        huge = "are you sure about this? " + ("the value is either x or y in this config line\n" * 24000)
        started = time.monotonic()
        result = correction_detector.detect(huge)
        elapsed = time.monotonic() - started
        self.assertIsNone(result)
        self.assertLess(elapsed, 2.0)

    def test_when_correction_cue_is_beyond_cap_should_not_fire(self):
        padding = "neutral context line\n" * 2000
        self.assertIsNone(correction_detector.detect(padding + "I didn't ask you to commit"))

    def test_when_are_you_sure_followup_is_far_beyond_window_should_not_fire(self):
        prompt = "are you sure? " + ("filler word soup with no cues here\n" * 40) + "or maybe just guess"
        self.assertIsNone(correction_detector.detect(prompt))


def _run_perturn_recall(root: Path, prompt: str) -> dict:
    workspace = root / "workspace"
    workspace.mkdir()
    deployed = _deploy_hooks(root)
    env = dict(os.environ)
    env["AGENT_MEMORY_SPEC_ROOT"] = str(root / "specs")
    env["AGENT_MEMORY_MIRROR_ROOT"] = str(root / "mirror")
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    result = subprocess.run(
        [sys.executable, str(deployed / "perturn_recall.py")],
        input=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "workspace_roots": [str(workspace)],
                "session_id": "correction-detector-test",
                "prompt": prompt,
            }
        ),
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        check=True,
    )
    return json.loads(result.stdout or "{}")


class TestPerturnRecallCorrectionInjection(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_when_recall_finds_nothing_but_prompt_fires_should_emit_directive_context(self):
        result = _run_perturn_recall(self.root, "did you really measure that or was it hallucinated?")

        context = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("User correction signal: unverified-claim", context)
        self.assertIn(",agent-memory note anti_pattern", context)
        self.assertNotIn("Relevant Learnings", context)
        # Cursor reads only the top-level snake key from beforeSubmitPrompt output.
        self.assertEqual(result["additional_context"], context)

    def test_when_prompt_does_not_fire_and_recall_finds_nothing_should_emit_empty_result(self):
        result = _run_perturn_recall(self.root, "why did you choose sqlite here?")

        self.assertEqual(result, {})

    def test_when_detector_raises_should_fail_open_with_valid_hook_output(self):
        root = self.root
        workspace = root / "workspace"
        workspace.mkdir()
        deployed = _deploy_hooks(root)
        sys.path.insert(0, str(deployed))
        self.addCleanup(lambda: sys.path.remove(str(deployed)) if str(deployed) in sys.path else None)

        loader = SourceFileLoader("perturn_recall_raise_test", str(deployed / "perturn_recall.py"))
        spec = importlib.util.spec_from_loader("perturn_recall_raise_test", loader)
        if spec is None or spec.loader is None:
            raise AssertionError("could not load perturn recall")
        module = importlib.util.module_from_spec(spec)
        sys.modules["perturn_recall_raise_test"] = module
        spec.loader.exec_module(module)

        def raise_detector(_prompt: str) -> str | None:
            raise RuntimeError("detector exploded")

        payload = {
            "hook_event_name": "UserPromptSubmit",
            "workspace_roots": [str(workspace)],
            "session_id": "correction-detector-raise-test",
            "prompt": "did you really measure that or was it hallucinated?",
        }
        stdout = io.StringIO()
        with (
            mock.patch.object(module.correction_detector, "detect", raise_detector),
            mock.patch.dict(
                os.environ,
                {
                    "AGENT_MEMORY_SPEC_ROOT": str(root / "specs"),
                    "AGENT_MEMORY_MIRROR_ROOT": str(root / "mirror"),
                    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                },
            ),
            mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            mock.patch.object(sys, "stdout", stdout),
        ):
            module.main()

        self.assertEqual(json.loads(stdout.getvalue() or "{}"), {})
