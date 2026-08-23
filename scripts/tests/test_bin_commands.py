#!/usr/bin/env python3
"""Compatibility aggregator for the split bin command test shards."""

from __future__ import annotations

import unittest

from .test_artifact import *  # noqa: F401,F403
from .test_codex import *  # noqa: F401,F403
from .test_copilot import *  # noqa: F401,F403
from .test_cursor import *  # noqa: F401,F403
from .test_cursor_llama_cpp import *  # noqa: F401,F403
from .test_install_yarn_pkgs import *  # noqa: F401,F403
from .test_kbn_stack import *  # noqa: F401,F403
from .test_mcp_token import *  # noqa: F401,F403
from .test_openrouter_wrappers import *  # noqa: F401,F403
from .test_unwrap_md import *  # noqa: F401,F403
from .test_w_issue import *  # noqa: F401,F403

if __name__ == "__main__":
    unittest.main()
