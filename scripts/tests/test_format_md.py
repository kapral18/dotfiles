#!/usr/bin/env python3
"""Focused tests for conservative Markdown formatting."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestFormatMdCommand(unittest.TestCase):
    """WHEN formatting Markdown prose."""

    def test_SHOULD_preserve_all_non_ai_contents_without_a_path_or_with_an_ordinary_path(self):
        format_md = _load_format_md_command()
        text = (
            "---\ndescription: >-\n  Keep this metadata\n  on its original lines.\n---\n\n"
            "Keep this hard break.  \nAnd this one\\\ncontinued here.\n\n"
            "```text\ntrailing spaces  \n```\n\n\n"
        )
        for path in (None, "", "docs/guide.md", "docs/.conform.123.guide.md"):
            with self.subTest(path=path):
                self.assertEqual(format_md.unwrap(text, path), text)

    def test_SHOULD_join_ai_continuations_only_when_the_complete_line_fits(self):
        format_md = _load_format_md_command()
        first = "Keep " + "a" * 100
        for count, should_join in ((33, True), (34, False)):
            second = "b" * count + "."
            text = first + "\n" + second + "\n"
            expected = first + (" " if should_join else "\n") + second + "\n"
            with self.subTest(count=count):
                actual = format_md.unwrap(text, "AGENTS.md")
                self.assertEqual(actual, expected)
                self.assertEqual(format_md.unwrap(actual, "AGENTS.md"), expected)

    def test_SHOULD_preserve_authored_ai_sentence_clause_and_indentation_boundaries(self):
        format_md = _load_format_md_command()
        examples = (
            "Keep this rule.\nnext comes an exception.\n",
            'Keep this rule!"\nNext comes an exception.\n',
            "Keep this rule;\nand keep its qualifier.\n",
            "Use examples, e.g.\nthese specific cases.\n",
            "- Keep this rule.\n  Retain this exception.\n",
            "Keep this rule\n  with different indentation.\n",
        )
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(format_md.unwrap(text, "AGENTS.md"), text)

    def test_SHOULD_leave_ambiguous_ai_markup_and_explicit_breaks_untouched(self):
        format_md = _load_format_md_command()
        examples = (
            "Keep this break  \ncontinued here.\n",
            "Keep this break\\\ncontinued here.\n",
            "Use `some command`\nwith these arguments.\n",
            "Use [this link](https://example.com)\nfor more information.\n",
            "Visit https://example.com\nfor more information.\n",
            "Use <span>this text</span>\nwith this qualifier.\n",
            "    code line one  \n    code line two\n",
            "- Example\n      code line one  \n      code line two\n",
            "| Heading |\n| --- |\n| Content |\n\n\n",
            "First | Second\n--- | ---\nOne | Two\nThree | Four\n",
            "A heading\n=========\nNext paragraph.\n",
            "A long heading sentence with enough words to approach the configured soft boundary and still stay intact as a heading. Another heading sentence.\n========\n",
            "Before a rule\n___\nAfter a rule.\n",
        )
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(format_md.unwrap(text, "AGENTS.md"), text)

    def test_SHOULD_preserve_ai_fence_contents_until_a_matching_close(self):
        format_md = _load_format_md_command()
        for opener, inner, closer in (("````md", "```", "````"), ("```text", "~~~", "```")):
            text = f"{opener}\n{inner}\nKeep these lines\nseparate.  \n{closer}\n"
            with self.subTest(opener=opener):
                self.assertEqual(format_md.unwrap(text, "AGENTS.md"), text)
        unclosed = "```text\nKeep these lines\nseparate.  \n"
        self.assertEqual(format_md.unwrap(unclosed, "AGENTS.md"), unclosed)

    def test_SHOULD_resume_ai_prose_after_frontmatter_or_a_fence(self):
        format_md = _load_format_md_command()
        for metadata in (
            "---\ndescription: Keep spaces  \n---\n",
            "---\ndescription: Keep spaces  \n...\n",
            "```text\nKeep spaces  \n```\n",
        ):
            text = metadata + "\nJoin this\ncontinuation.\n\n"
            with self.subTest(metadata=metadata):
                self.assertEqual(format_md.unwrap(text, "AGENTS.md"), metadata + "\nJoin this continuation.\n\n")
        unclosed = "---\ndescription: >-\n  Keep these lines\n  separate.  \n"
        self.assertEqual(format_md.unwrap(unclosed, "AGENTS.md"), unclosed)

    def test_SHOULD_soft_wrap_recognized_instruction_surfaces(self):
        format_md = _load_format_md_command()
        sentence = "Keep all of the exact original words and retain every condition in this sentence."
        text = f"{sentence} {sentence}\n"
        expected = f"{sentence}\n{sentence}\n"
        paths = (
            ".agents/references/guide.md",
            ".github/instructions/react.instructions.md",
            "/repo/.agents/references/guide.md",
            "/repo/.github/instructions/react.instructions.md",
            "home/exact_dot_agents/exact_references/readonly_guide.md",
            "/repo/.agents/references/.conform.123.guide.md",
            "/repo/.github/instructions/.conform.123.react.instructions.md",
            r"C:\repo\.agents\references\guide.md",
            r"C:\repo\.github\instructions\react.instructions.md",
            "SKILL.md",
            "readonly_SKILL.md",
            ".github/copilot-instructions.md",
            ".copilot/copilot-instructions.md",
            "readonly_copilot-instructions.md",
            ".conform.123.copilot-instructions.md",
            "home/dot_claude/exact_agents/guide.md",
            ".claude/agents/guide.md",
            ".codex/skills/example/references/guide.md",
            ".cursor/skills/example/references/guide.md",
            ".cursor/agents/guide.md",
            ".cursor/plugins/local/k-sop/rules/sop.md",
            ".copilot/skills/example/references/guide.md",
            ".copilot/agents/guide.agent.md",
            ".gemini/config/skills/example/references/guide.md",
            ".omp/agent/skills/example/references/guide.md",
            ".omp/agent/agents/guide.md",
            ".pi/agent/agents/guide.md",
            ".config/opencode/skills/example/references/guide.md",
        )
        for path in paths:
            with self.subTest(path=path):
                result = format_md.unwrap(text, path)
                self.assertEqual(result, expected)
                self.assertEqual(format_md.unwrap(result, path), expected)

    def test_SHOULD_preserve_metadata_code_tables_and_urls_in_new_ai_paths(self):
        format_md = _load_format_md_command()
        text = (
            "---\ndescription: >-\n  Keep this metadata\n  on its original lines.\n---\n\n"
            "```sh\n" + "echo " + "x" * 160 + "\n```\n\n"
            "| Heading |\n| --- |\n| " + "x" * 160 + " |\n\n"
            "https://example.com/" + "x" * 160 + "\n"
        )
        for path in (
            ".agents/references/guide.md",
            ".github/instructions/react.instructions.md",
            "home/exact_dot_agents/exact_references/readonly_guide.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(format_md.unwrap(text, path), text)

    def test_SHOULD_preserve_contents_outside_instruction_markers(self):
        format_md = _load_format_md_command()
        text = "A paragraph\ncontinued here.\n"
        for path in (
            "docs/references/guide.md",
            ".agents/references-other/guide.md",
            ".github/instructions-other/guide.md",
            ".agents/references/guide.txt",
            ".claude/agents/guide.md.tmpl",
            ".codex/agents/guide.toml",
            ".agents/plans/guide.md",
            "docs/agents/guide.md",
            "docs/skills/guide.md",
            ".cursor/skills-other/guide.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(format_md.preserves_hard_wraps(path))
                self.assertEqual(format_md.unwrap(text, path), text)

    def test_SHOULD_preserve_regular_markdown_paragraphs(self):
        format_md = _load_format_md_command()
        text = "This is one paragraph\nthat was hard wrapped.\n\n- Keep list items\n  structural.\n"

        result = format_md.unwrap(text, "docs/topics/example.md")

        assert result == text

    def test_SHOULD_preserve_sop_sentence_breaks(self):
        format_md = _load_format_md_command()
        text = "Keep this gate visible.\nDo not hide it later in the same line.\n"

        result = format_md.unwrap(text, "home/readonly_AGENTS.md")

        assert result == text

    def test_normalizes_conform_temp_sop_entrypoint_as_ai_markdown(self):
        format_md = _load_format_md_command()
        text = (
            "This SOP is not optional guidance — it is a binding operational contract. "
            "Every instruction herein MUST be followed to the letter, without exception.\n"
        )

        result = format_md.unwrap(text, "home/.conform.1234567.readonly_AGENTS.md")

        assert result == (
            "This SOP is not optional guidance — it is a binding operational contract.\n"
            "Every instruction herein MUST be followed to the letter, without exception.\n"
        )

    def test_SHOULD_preserve_skill_sentence_breaks(self):
        format_md = _load_format_md_command()
        text = "Use when the exact trigger matches.\nLoad the skill before acting.\n"

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == text

    def test_normalizes_skill_instruction_wraps_without_splitting_short_lines(self):
        format_md = _load_format_md_command()
        text = "Finish a sentence before moving\nto the next line. Start the next sentence on its own line.\n"

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == "Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"

    def test_normalizes_skill_list_items_without_splitting_short_lines(self):
        format_md = _load_format_md_command()
        text = "- Finish a sentence before moving\n  to the next line. Start the next sentence on its own line.\n"

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert (
            result == "- Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"
        )

    def test_preserves_indented_skill_prose_prefixes(self):
        format_md = _load_format_md_command()
        text = "   Finish a sentence before moving\n   to the next line. Start the next sentence on its own line.\n"

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert (
            result == "   Finish a sentence before moving to the next line. Start the next sentence on its own line.\n"
        )

    def test_wraps_skill_prose_at_sentence_boundary_over_soft_limit(self):
        format_md = _load_format_md_command()
        text = (
            "This sentence is deliberately long enough that appending the next sentence would cross the formatter boundary "
            "without needing to split this sentence. Start the next sentence on its own line.\n"
        )

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == (
            "This sentence is deliberately long enough that appending the next sentence would cross the formatter boundary without needing to split this sentence.\n"
            "Start the next sentence on its own line.\n"
        )

    def test_wraps_single_long_skill_sentence_at_clause_boundary(self):
        format_md = _load_format_md_command()
        text = (
            "Keep the review gate visible for the controller because workers cannot mutate shared state safely; "
            "and return verification needs instead of running destructive probes inside parallel lanes.\n"
        )

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == (
            "Keep the review gate visible for the controller because workers cannot mutate shared state safely;\n"
            "and return verification needs instead of running destructive probes inside parallel lanes.\n"
        )

    def test_keeps_single_long_skill_sentence_without_strong_clause_boundary(self):
        format_md = _load_format_md_command()
        text = (
            "Review documentation updates preserve routing metadata through generated summaries across delegated workflows "
            "to keep every prompt input readable during later audits while retaining the exact details reviewers need.\n"
        )

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == text

    def test_preserves_multiline_inline_code_examples(self):
        format_md = _load_format_md_command()
        text = "- `First sentence. Second sentence\nwithout closing until here.`\n"

        result = format_md.unwrap(text, "home/readonly_AGENTS.md")

        assert result == text

    def test_does_not_split_common_abbreviations_as_skill_sentences(self):
        format_md = _load_format_md_command()
        text = 'Use examples, e.g. "the review skill", before acting. Then continue.\n'

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md")

        assert result == 'Use examples, e.g. "the review skill", before acting. Then continue.\n'

    def test_SHOULD_preserve_reference_sentence_breaks(self):
        format_md = _load_format_md_command()
        text = "Keep the review gate visible.\nDo not bury it after another clause.\n"

        result = format_md.unwrap(
            text,
            "home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_pr_common.md",
        )

        assert result == text

    def test_SHOULD_preserve_hook_sentence_breaks(self):
        format_md = _load_format_md_command()
        text = "Keep hook behavior visible.\nDo not collapse support instructions.\n"

        result = format_md.unwrap(text, "home/exact_dot_agents/exact_hooks/readonly_README.md")

        assert result == text


if __name__ == "__main__":
    unittest.main()
