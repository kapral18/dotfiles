#!/usr/bin/env python3
"""Focused tests for unwrap md."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestUnwrapMdCommand(unittest.TestCase):
    """WHEN unwrapping markdown prose."""

    def test_unwraps_regular_markdown_paragraphs(self):
        unwrap_md = _load_unwrap_md_command()
        text = "This is one paragraph\nthat was hard wrapped.\n\n- Keep list items\n  structural.\n"

        result = unwrap_md.unwrap(text, "docs/topics/example.md")

        assert result == "This is one paragraph that was hard wrapped.\n\n- Keep list items structural.\n"

    def test_normalizes_sop_instruction_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Keep this gate visible.\nDo not hide it later in the same line.\n"

        result = unwrap_md.unwrap(text, "home/readonly_AGENTS.md")

        assert result == "Keep this gate visible. Do not hide it later in the same line.\n"

    def test_normalizes_conform_temp_sop_entrypoint_as_ai_markdown(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "This SOP is not optional guidance — it is a binding operational contract. "
            "Every instruction herein MUST be followed to the letter, without exception.\n"
        )

        result = unwrap_md.unwrap(text, "home/.conform.1234567.readonly_AGENTS.md")

        assert result == (
            "This SOP is not optional guidance — it is a binding operational contract.\n"
            "Every instruction herein MUST be followed to the letter, without exception.\n"
        )

    def test_normalizes_skill_instruction_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Use when the exact trigger matches.\nLoad the skill before acting.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == "Use when the exact trigger matches. Load the skill before acting.\n"

    def test_normalizes_skill_instruction_wraps_without_splitting_short_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Finish a sentence before moving\nto the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == "Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"

    def test_normalizes_skill_list_items_without_splitting_short_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "- Finish a sentence before moving\n  to the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert (
            result == "- Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"
        )

    def test_preserves_indented_skill_prose_prefixes(self):
        unwrap_md = _load_unwrap_md_command()
        text = "   Finish a sentence before moving\n   to the next line. Start the next sentence on its own line.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert (
            result == "   Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"
        )

    def test_wraps_skill_prose_at_sentence_boundary_over_soft_limit(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "This sentence is deliberately long enough that appending the next sentence would cross the formatter boundary "
            "without needing to split this sentence. Start the next sentence on its own line.\n"
        )

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == (
            "This sentence is deliberately long enough that appending the next sentence would cross the formatter boundary without needing to split this sentence.\n"
            "Start the next sentence on its own line.\n"
        )

    def test_wraps_single_long_skill_sentence_at_clause_boundary(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "Keep the review gate visible for the controller because workers cannot mutate shared state safely; "
            "and return verification needs instead of running destructive probes inside parallel lanes.\n"
        )

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == (
            "Keep the review gate visible for the controller because workers cannot mutate shared state safely;\n"
            "and return verification needs instead of running destructive probes inside parallel lanes.\n"
        )

    def test_keeps_single_long_skill_sentence_without_strong_clause_boundary(self):
        unwrap_md = _load_unwrap_md_command()
        text = (
            "Review documentation updates preserve routing metadata through generated summaries across delegated workflows "
            "to keep every prompt input readable during later audits while retaining the exact details reviewers need.\n"
        )

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == text

    def test_preserves_multiline_inline_code_examples(self):
        unwrap_md = _load_unwrap_md_command()
        text = "- `First sentence. Second sentence\nwithout closing until here.`\n"

        result = unwrap_md.unwrap(text, "home/readonly_AGENTS.md")

        assert result == text

    def test_does_not_split_common_abbreviations_as_skill_sentences(self):
        unwrap_md = _load_unwrap_md_command()
        text = 'Use examples, e.g. "the review skill", before acting. Then continue.\n'

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == 'Use examples, e.g. "the review skill", before acting. Then continue.\n'

    def test_normalizes_skill_reference_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Keep the review gate visible.\nDo not bury it after another clause.\n"

        result = unwrap_md.unwrap(
            text,
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_common.md",
        )

        assert result == "Keep the review gate visible. Do not bury it after another clause.\n"

    def test_normalizes_agent_hook_short_sentence_lines(self):
        unwrap_md = _load_unwrap_md_command()
        text = "Keep hook behavior visible.\nDo not collapse support instructions.\n"

        result = unwrap_md.unwrap(text, "home/exact_dot_agents/exact_hooks/readonly_README.md")

        assert result == "Keep hook behavior visible. Do not collapse support instructions.\n"


if __name__ == "__main__":
    unittest.main()
