"""Citation checks distinguish report claims from Markdown examples."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "home/exact_lib/exact_,task/evidence.py"
SPEC = importlib.util.spec_from_file_location("task_evidence", SOURCE)
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class TestReportEvidence(unittest.TestCase):
    def test_WHEN_examples_are_nested_SHOULD_ignore_their_claims(self):
        cases = (
            "- Example:\n\n    ```md\n    Checked: sample [C999]\n    ```",
            "- Outer\n  1. Example:\n\n      ~~~\n      Checked: sample [C999]\n      ~~~",
            "- ```md\n  Checked: sample [C999]\n  ```",
            "> Quoted paragraph.\nChecked: sample [C999]",
            "- Quote:\n\n  > Quoted paragraph.\n  Checked: sample [C999]",
        )
        for answer in cases:
            with self.subTest(answer=answer):
                self.assertEqual(evidence.check_answer({"claims": [], "done": []}, answer, []), [])

    def test_WHEN_an_example_ends_SHOULD_check_the_following_real_claim(self):
        cases = (
            "- ```md\n  Checked: sample [C888]\n  ```\n\nChecked: actual [C999]",
            "- ```md\n  Checked: sample [C888]\nChecked: actual [C999]",
            "> Quoted paragraph.\nChecked: sample [C888]\n\nChecked: actual [C999]",
            "> ```md\n> Checked: sample [C888]\nChecked: actual [C999]",
            "> <div>\nChecked: actual [C999]",
            "> <!--\nChecked: actual [C999]",
        )
        for answer in cases:
            with self.subTest(answer=answer):
                self.assertEqual(evidence.check_answer({"claims": [], "done": []}, answer, []), ["unknown C999"])

    def test_WHEN_a_report_contains_only_an_example_SHOULD_require_real_evidence(self):
        answer = "Checked:\n- ```md\n  - sample [C999]\n  ```"
        self.assertEqual(
            evidence.check_answer({"claims": [], "done": []}, answer, []),
            ["Checked: each item needs a [C<n>] citation: "],
        )

    def test_WHEN_a_report_is_a_list_item_SHOULD_check_its_citation(self):
        answer = "- Checked:\n  - actual [C999]"
        self.assertEqual(evidence.check_answer({"claims": [], "done": []}, answer, []), ["unknown C999"])


if __name__ == "__main__":
    unittest.main()
