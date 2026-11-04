#!/usr/bin/env python3
"""Verify presentation assembly against independent byte-preserving edits."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from _test_support import REPO

SKILL = REPO / "home/exact_dot_agents/exact_skills/exact_k-present-pr"
HELPER = SKILL / "exact_scripts/readonly_template.py"
TEMPLATE = SKILL / "exact_references/readonly_template.html"


class TestPresentationTemplate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.draft = self.directory / "draft.html"
        self.output = self.directory / "presentation.html"

    def run_helper(self, *args):
        return subprocess.run(
            [sys.executable, str(HELPER), *map(str, args)],
            capture_output=True,
            check=False,
        )

    def prepare(self):
        result = self.run_helper("prepare", TEMPLATE, self.draft)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_round_trip_is_byte_identical(self):
        self.prepare()
        result = self.run_helper("render", TEMPLATE, self.draft, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), TEMPLATE.read_bytes())
        self.assertNotIn(b"<style>", self.draft.read_bytes())
        self.assertNotIn(b"<script>", self.draft.read_bytes())

    def test_content_edits_match_direct_template_edits(self):
        self.prepare()
        draft = self.draft.read_bytes()
        template = TEMPLATE.read_bytes()
        # Independent changes exercise arbitrary text, Unicode and new blocks.
        for before, after in (
            (b"</title>", " — example</title>".encode()),
            (b"</body>", b'<section id="extra">&lt;real diff&gt;</section></body>'),
            (
                b"</body>",
                b"<pre><code>b&quot;&lt;!-- K_PRESENT_PR_FIXED_STYLE --&gt;&quot;</code></pre></body>",
            ),
        ):
            self.assertEqual(draft.count(before), 1)
            self.assertEqual(template.count(before), 1)
            draft = draft.replace(before, after)
            template = template.replace(before, after)
        self.draft.write_bytes(draft)
        result = self.run_helper("render", TEMPLATE, self.draft, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), template)

    def test_invalid_markers_leave_existing_output_untouched(self):
        self.prepare()
        draft = self.draft.read_bytes()
        cases = {
            "unknown": draft + b"<!-- K_PRESENT_PR_FIXED_OTHER -->",
            "unknown-with-whitespace": draft + b"<!--\n K_PRESENT_PR_FIXED_OTHER -->",
            "extra-damaged": draft + b"<!-- K_PRESENT_PR_FIXED_STYLE --!>",
        }
        for tag in (b"STYLE", b"SCRIPT"):
            marker = b"<!-- K_PRESENT_PR_FIXED_" + tag + b" -->"
            self.assertIn(marker, draft)
            cases.update(
                {
                    (tag, "missing"): draft.replace(marker, b""),
                    (tag, "duplicate"): draft + marker,
                    (tag, "damaged"): draft.replace(marker, marker.replace(b"-->", b"--!>")),
                }
            )
        for name, content in cases.items():
            with self.subTest(name=name):
                self.output.write_bytes(b"existing presentation")
                self.draft.write_bytes(content)
                result = self.run_helper("render", TEMPLATE, self.draft, self.output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.output.read_bytes(), b"existing presentation")

    def test_invalid_template_and_input_alias_do_not_overwrite(self):
        template = self.directory / "template.html"
        valid = b"<html><style>body{}</style><script>x</script></html>"
        for block in (b"<style>body{}</style>", b"<script>x</script>"):
            for count in (0, 2):
                with self.subTest(block=block, count=count):
                    template.write_bytes(valid.replace(block, block * count))
                    result = self.run_helper("prepare", template, self.draft)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"template must contain exactly one", result.stderr)
                    self.assertFalse(self.draft.exists())
        # A valid template ensures alias rejection, not parsing failure, protects it.
        original = valid
        template.write_bytes(original)
        alias = self.directory / "alias.html"
        alias.symlink_to(template)
        result = self.run_helper("prepare", template, alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(template.read_bytes(), original)
        alias.unlink()
        os.link(template, alias)
        result = self.run_helper("prepare", template, alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(template.read_bytes(), original)

    def test_when_template_contains_reserved_marker_should_reject_without_writing(self):
        template = self.directory / "template.html"
        for tag in (b"STYLE", b"SCRIPT"):
            with self.subTest(tag=tag):
                template.write_bytes(b"<style>body{}</style><script>x</script><!-- K_PRESENT_PR_FIXED_" + tag + b" -->")
                self.draft.write_bytes(b"existing draft")
                result = self.run_helper("prepare", template, self.draft)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"reserved editing marker", result.stderr)
                self.assertEqual(self.draft.read_bytes(), b"existing draft")

    def test_when_tags_have_mixed_case_should_preserve_original_bytes(self):
        template = self.directory / "template.html"
        original = b'<STYLE media="all">body{}</STYLE><ScRiPt>\nx\n</sCrIpT>'
        template.write_bytes(original)
        result = self.run_helper("prepare", template, self.draft)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b"body{}", self.draft.read_bytes())
        self.assertNotIn(b"\nx\n", self.draft.read_bytes())
        result = self.run_helper("render", template, self.draft, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), original)

    def test_when_render_output_aliases_input_should_reject_without_writing(self):
        template = self.directory / "template.html"
        template.write_bytes(b"<style>body{}</style><script>x</script>")
        result = self.run_helper("prepare", template, self.draft)
        self.assertEqual(result.returncode, 0, result.stderr)
        for source in (template, self.draft):
            for kind in ("same-path", "symlink", "hardlink"):
                with self.subTest(source=source.name, kind=kind):
                    original = source.read_bytes()
                    alias = self.directory / "alias.html"
                    if kind == "same-path":
                        destination = source
                    else:
                        destination = alias
                        if kind == "symlink":
                            alias.symlink_to(source)
                        else:
                            os.link(source, alias)
                    result = self.run_helper("render", template, self.draft, destination)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"output must be separate from its inputs", result.stderr)
                    self.assertEqual(source.read_bytes(), original)
                    if kind != "same-path":
                        alias.unlink()

    def test_when_missing_input_aliases_output_should_report_input_output_conflict(self):
        missing = self.directory / "missing.html"
        alias = self.directory / "alias.html"
        alias.symlink_to(missing)
        for destination in (missing, alias):
            with self.subTest(destination=destination.name):
                result = self.run_helper("prepare", missing, destination)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"output must be separate from its inputs", result.stderr)
                self.assertFalse(missing.exists())


class TemplateDocument(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.root = {"tag": "document", "attrs": {}, "children": [], "parent": None}
        self.current = self.root
        self.nodes = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": [], "parent": self.current}
        self.current["children"].append(node)
        self.nodes.append(node)
        if tag not in {"meta", "link", "img", "br", "hr", "input"}:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node["parent"] is not None:
            if node["tag"] == tag:
                self.current = node["parent"]
                break
            node = node["parent"]

    def handle_data(self, data):
        self.current["children"].append(data)


def stylesheet_rules(source, conditions=()):
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    cursor = 0
    while cursor < len(source):
        opening = source.find("{", cursor)
        if opening < 0:
            return
        selector = source[cursor:opening].strip()
        depth, closing = 1, opening + 1
        while depth:
            depth += (source[closing] == "{") - (source[closing] == "}")
            closing += 1
        body = source[opening + 1 : closing - 1]
        cursor = closing
        if selector.startswith("@media"):
            yield from stylesheet_rules(body, conditions + (selector,))
        elif not selector.startswith("@"):
            declarations = dict(item.split(":", 1) for item in body.split(";") if ":" in item)
            for item in selector.split(","):
                yield conditions, item.strip(), declarations


def selector_matches(node, selector, state=""):
    parts = selector.split()

    def matches(candidate, part):
        pseudo = re.search(r"::(before|after)", part)
        if (pseudo.group(1) if pseudo else "") != candidate.get("pseudo", ""):
            return False
        part = re.sub(r"::(?:before|after)", "", part)
        for required in re.findall(r":(hover|focus-visible)", part):
            if required != state:
                return False
        part = re.sub(r":[\w-]+(?:\([^)]*\))?", "", part)
        tag = re.match(r"^[\w-]+", part)
        if tag and candidate["tag"] != tag.group():
            return False
        attrs = candidate["attrs"]
        return all(attrs.get("id") == value for value in re.findall(r"#([\w-]+)", part)) and all(
            value in attrs.get("class", "").split() for value in re.findall(r"\.([\w-]+)", part)
        )

    if not matches(node, parts[-1]):
        return False
    ancestor = node["parent"]
    for part in reversed(parts[:-1]):
        while ancestor is not None and not matches(ancestor, part):
            ancestor = ancestor["parent"]
        if ancestor is None:
            return False
        ancestor = ancestor["parent"]
    return True


def computed_style(node, rules, width, reduced=False, state=""):
    values = {}
    for order, (conditions, selector, declarations) in enumerate(rules):
        applies = True
        for condition in conditions:
            for bound, value in re.findall(r"(min|max)-width\s*:\s*(\d+)px", condition):
                applies &= width >= int(value) if bound == "min" else width <= int(value)
            if "prefers-reduced-motion" in condition:
                applies &= reduced
        if not applies or not selector_matches(node, selector, state):
            continue
        specificity = (
            selector.count("#"),
            len(re.findall(r"[.:](?!:)[\w-]+", selector)),
            len(re.findall(r"(?:^|\s)[a-z]+", selector)),
        )
        for key, value in declarations.items():
            priority = ("!important" in value, *specificity, order)
            if key.strip() not in values or priority >= values[key.strip()][0]:
                values[key.strip()] = priority, value.replace("!important", "").strip()
    return {key: value for key, (_, value) in values.items()}


class PresentationAccessibilityTests(unittest.TestCase):
    def setUp(self):
        source = TEMPLATE.read_text()
        self.document = TemplateDocument(source)
        self.rules = list(stylesheet_rules(source.split("<style>", 1)[1].split("</style>", 1)[0]))

    def name(self, node, width):
        if isinstance(node, str):
            return node
        if computed_style(node, self.rules, width).get("display") == "none":
            return ""
        return node["attrs"].get("aria-label") or "".join(self.name(child, width) for child in node["children"])

    def test_hidden_rail_is_unavailable_until_its_navigation_is_visible(self):
        rail = next(node for node in self.document.nodes if node["attrs"].get("id") == "rail")
        for width in [1025, 1100, 1319]:
            self.assertEqual(computed_style(rail, self.rules, width).get("visibility", "visible"), "hidden")
        rail["attrs"]["class"] = "show"
        for width in [1025, 1100, 1319]:
            self.assertEqual(computed_style(rail, self.rules, width).get("visibility", "visible"), "visible")

    def test_visible_rail_links_keep_names_when_the_viewport_hides_the_sidebars(self):
        rail = next(node for node in self.document.nodes if node["attrs"].get("id") == "rail")
        rail["attrs"]["class"] = "show"
        links = [node for node in rail["children"] if isinstance(node, dict) and node["tag"] == "a"]
        self.assertTrue(links)
        for width in [1025, 1100, 1319]:
            self.assertNotEqual(computed_style(rail, self.rules, width).get("display"), "none")
            for link in links:
                self.assertTrue(self.name(link, width).strip(), f"unnamed rail link at {width}px")
                text = next(
                    child
                    for child in link["children"]
                    if isinstance(child, dict) and "rtxt" in child["attrs"].get("class", "")
                )
                self.assertEqual(computed_style(text, self.rules, width, state="focus-visible").get("opacity"), "1")

    def test_reduced_motion_stops_animation_and_keeps_entrance_content_visible(self):
        html = next(node for node in self.document.nodes if node["tag"] == "html")
        self.assertEqual(computed_style(html, self.rules, 1100, reduced=True).get("scroll-behavior"), "auto")
        animated = []
        for node in self.document.nodes:
            for pseudo in ["", "before", "after"]:
                candidate = node | {"pseudo": pseudo}
                normal = computed_style(candidate, self.rules, 1100)
                if normal.get("animation", "none") != "none":
                    animated.append(candidate)
                    reduced = computed_style(candidate, self.rules, 1100, reduced=True)
                    self.assertEqual(reduced.get("animation"), "none", node["attrs"])
                    self.assertEqual(reduced.get("transition"), "none", node["attrs"])
                    if normal.get("opacity") == "0":
                        self.assertEqual(reduced.get("opacity"), "1", node["attrs"])
        self.assertTrue(animated, "the fixture must exercise its animated elements")
        reveals = [node for node in self.document.nodes if "reveal" in node["attrs"].get("class", "").split()]
        self.assertTrue(reveals)
        for node in reveals:
            self.assertEqual(computed_style(node, self.rules, 1100, reduced=True).get("opacity"), "1")


if __name__ == "__main__":
    unittest.main()
