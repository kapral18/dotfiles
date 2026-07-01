#!/usr/bin/env python3
"""Tests for embed.py helper behavior."""

from __future__ import annotations

import unittest

import _test_support  # noqa: F401  (puts scripts/ on sys.path)


class TestEmbedModuleHelpers(unittest.TestCase):
    """Small unit tests for the embed module helpers that don't need
    the runner: pack/unpack, cosine math, default constants."""

    def test_pack_unpack_roundtrip(self):
        import embed

        v = [0.1, -0.5, 1.234, 0.0, -1e-3]
        blob = embed.pack_vector(v)
        assert len(blob) == len(v) * 4
        out = embed.unpack_vector(blob)
        assert len(out) == len(v)
        for a, b in zip(v, out):
            assert abs(a - b) < 1e-6

    def test_unpack_handles_none_and_empty(self):
        import embed

        assert embed.unpack_vector(None) == []
        assert embed.unpack_vector(b"") == []

    def test_cosine_basic_math(self):
        import embed

        assert embed.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
        assert abs(embed.cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9
        assert embed.cosine([], [1.0]) == 0.0
        assert embed.cosine([1.0], [1.0, 2.0]) == 0.0  # length mismatch


if __name__ == "__main__":
    unittest.main()
