#!/usr/bin/env python3
"""Tests for `,ai-usage`: cost-weighted token usage from local harness records.

Fixture shapes mirror real local records observed on 2026-09-06: Claude Code transcripts
(message.usage + requestId), Codex rollouts (token_count events), Pi and OMP session
JSONL (usage with input/cacheRead/cacheWrite), and the OpenCode sqlite session table.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

import _test_support  # noqa: F401
from _test_support import REPO

CORE = REPO / "home" / "exact_lib" / "exact_,ai-usage" / "main.py"
LAUNCHER = REPO / "home" / "exact_bin" / "executable_,ai-usage"
COMPLETION = REPO / "home" / "dot_config" / "fish" / "completions" / "readonly_,ai-usage.fish"


def load_core():
    spec = importlib.util.spec_from_file_location("ai_usage_core", CORE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


class AiUsageReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["AI_USAGE_HOME"] = str(self.home)
        self.core = load_core()
        self.now = "2026-09-06T10:00:00.000Z"

    def tearDown(self) -> None:
        os.environ.pop("AI_USAGE_HOME", None)
        self.tmp.cleanup()

    def test_claude_reader_dedupes_rows_that_share_a_request_and_splits_cache(self) -> None:
        usage = {
            "input_tokens": 2,
            "cache_read_input_tokens": 1000,
            "cache_creation_input_tokens": 30,
            "output_tokens": 50,
            "output_tokens_details": {"thinking_tokens": 20},
        }
        rows = [
            {"type": "user", "timestamp": self.now, "message": {"role": "user", "content": "hi"}},
            # Claude Code writes one row per content block; both rows share the request id.
            {"type": "assistant", "requestId": "req_1", "message": {"model": "claude-fable-5-1", "usage": usage}},
            {"type": "assistant", "requestId": "req_1", "message": {"model": "claude-fable-5-1", "usage": usage}},
            {"type": "assistant", "requestId": "req_2", "message": {"model": "claude-fable-5-1", "usage": usage}},
        ]
        write_jsonl(self.home / ".claude" / "projects" / "-ws" / "sess-a.jsonl", rows)

        (session,) = self.core.read_claude(0)
        self.assertEqual(
            (session.calls, session.fresh_input, session.cache_read, session.cache_write), (2, 4, 2000, 60)
        )
        self.assertEqual((session.output, session.reasoning, session.model), (100, 40, "claude-fable-5-1"))
        self.assertAlmostEqual(session.hit_rate, 2000 / 2064)

    def test_codex_reader_subtracts_cached_tokens_from_input_total(self) -> None:
        rows = [
            {"timestamp": self.now, "type": "session_meta", "payload": {"id": "sid-1", "timestamp": self.now}},
            {"type": "turn_context", "payload": {"model": "gpt-5.5"}},
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 5},
                        "total_token_usage": {
                            "input_tokens": 130264,
                            "cached_input_tokens": 97152,
                            "cache_write_input_tokens": 0,
                            "output_tokens": 2752,
                            "reasoning_output_tokens": 1727,
                        },
                    },
                },
            },
        ]
        write_jsonl(
            self.home / ".codex" / "sessions" / "2026" / "09" / "06" / "rollout-2026-09-06T01-26-29-sid-1.jsonl", rows
        )

        (session,) = self.core.read_codex(0)
        self.assertEqual(session.session_id, "sid-1")
        self.assertEqual((session.fresh_input, session.cache_read), (130264 - 97152, 97152))
        self.assertEqual((session.output, session.reasoning, session.model, session.calls), (2752, 1727, "gpt-5.5", 1))

    def test_pi_and_omp_readers_treat_input_as_fresh(self) -> None:
        usage = {"input": 1155, "output": 47, "cacheRead": 24835, "cacheWrite": 0, "reasoning": 3, "totalTokens": 26037}
        write_jsonl(
            self.home / ".pi" / "agent" / "sessions" / "ws" / "2026-09-02T20-08-52_abc.jsonl",
            [
                {
                    "type": "message",
                    "timestamp": self.now,
                    "message": {"role": "assistant", "provider": "llama-cpp", "model": "qwen", "usage": usage},
                }
            ],
        )
        write_jsonl(
            self.home / ".omp" / "agent" / "sessions" / "ws" / "2026-08-31T09-28-47_def.jsonl",
            [
                {"type": "session", "timestamp": self.now},
                {
                    "type": "message",
                    "timestamp": self.now,
                    "message": {
                        "role": "assistant",
                        "model": "gpt-5.5",
                        "provider": "openai-codex",
                        "usage": {
                            "input": 33486,
                            "output": 666,
                            "cacheRead": 10,
                            "cacheWrite": 0,
                            "reasoningTokens": 516,
                        },
                    },
                },
            ],
        )

        (pi,) = self.core.read_pi(0)
        self.assertEqual(
            (pi.fresh_input, pi.cache_read, pi.output, pi.reasoning, pi.provider), (1155, 24835, 47, 3, "llama-cpp")
        )
        (omp,) = self.core.read_omp(0)
        self.assertEqual((omp.fresh_input, omp.cache_read, omp.reasoning, omp.model), (33486, 10, 516, "gpt-5.5"))

    def test_SHOULD_subtract_codex_writes_from_totals_and_clamp_fresh(self) -> None:
        """WHEN inclusive Codex totals contain writes, context must not count them twice."""
        for writes, fresh, context in ((4, 6, 100), (0, 10, 100), (None, 10, 100), (20, 0, 110)):
            with self.subTest(writes=writes):
                usage = {
                    "input_tokens": 100,
                    "cached_input_tokens": 90,
                    "output_tokens": 5,
                    "reasoning_output_tokens": 2,
                }
                if writes is not None:
                    usage["cache_write_input_tokens"] = writes
                row = {
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "last_token_usage": usage,
                            "total_token_usage": usage,
                        },
                    },
                }
                write_jsonl(self.home / ".codex/sessions/2026/09/06/rollout-writes.jsonl", [row, row])
                (session,) = self.core.read_codex(0)
                self.assertEqual((session.fresh_input, session.context_tokens), (fresh, context))
                self.assertEqual(
                    (session.cache_read, session.cache_write, session.output, session.reasoning, session.calls),
                    (90, writes or 0, 5, 2, 1),
                )
                self.assertAlmostEqual(session.hit_rate, 90 / context)

    def test_SHOULD_use_inclusive_codex_context_for_call_miss_thresholds(self) -> None:
        """WHEN the next read is exactly half the prior context, writes must not invent a miss."""
        for cached, misses in ((50, 0), (49, 1)):
            with self.subTest(cached=cached):
                first = {
                    "input_tokens": 100,
                    "cached_input_tokens": 90,
                    "cache_write_input_tokens": 4,
                    "output_tokens": 5,
                }
                second = {
                    "input_tokens": 110,
                    "cached_input_tokens": cached,
                    "cache_write_input_tokens": 10,
                    "output_tokens": 6,
                }
                rows = [
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": usage,
                                "total_token_usage": second,
                            },
                        },
                    }
                    for usage in (first, first, second)
                ]
                write_jsonl(self.home / ".codex/sessions/2026/09/06/rollout-misses.jsonl", rows)
                (session,) = self.core.read_codex(0)
                self.assertEqual((session.calls, session.cache_misses), (2, misses))
                self.assertEqual(session._prev_context, 110)

    def test_opencode_reader_uses_session_rollups_and_counts_assistant_messages(self) -> None:
        db = self.home / ".local" / "share" / "opencode" / "opencode.db"
        db.parent.mkdir(parents=True)
        conn = sqlite3.connect(db)
        conn.execute(
            "create table session (id text, model text, time_created integer, time_updated integer, tokens_input integer, "
            "tokens_output integer, tokens_reasoning integer, tokens_cache_read integer, tokens_cache_write integer)"
        )
        conn.execute("create table message (id text, session_id text, time_created integer, data text)")
        now_ms = int(time.time() * 1000)
        conn.execute(
            "insert into session values (?,?,?,?,?,?,?,?,?)",
            (
                "ses_1",
                json.dumps({"id": "deepseek/deepseek-v4-flash", "providerID": "openrouter"}),
                now_ms,
                now_ms,
                5827,
                14,
                0,
                23104,
                0,
            ),
        )
        per_call = [
            {"input": 5000, "output": 10, "cache": {"read": 0, "write": 0}},
            {"input": 100, "output": 2, "cache": {"read": 5000, "write": 0}},
            # Cache lost: the whole prompt is fresh again.
            {"input": 5200, "output": 2, "cache": {"read": 0, "write": 0}},
        ]
        for i, tokens in enumerate(per_call):
            data = json.dumps({"role": "assistant", "tokens": tokens})
            conn.execute("insert into message values (?,?,?,?)", (f"m{i}", "ses_1", now_ms + i, data))
        conn.execute("insert into message values (?,?,?,?)", ("u1", "ses_1", now_ms, json.dumps({"role": "user"})))
        conn.commit()
        conn.close()

        (session,) = self.core.read_opencode(0)
        self.assertEqual((session.calls, session.fresh_input, session.cache_read, session.output), (3, 5827, 23104, 14))
        self.assertEqual(session.cache_misses, 1)
        self.assertEqual((session.model, session.provider), ("deepseek/deepseek-v4-flash", "openrouter"))

    def test_signals_view_counts_corrections_and_reinforcements(self) -> None:
        usage = {"input_tokens": 1, "cache_read_input_tokens": 9, "cache_creation_input_tokens": 0, "output_tokens": 1}
        write_jsonl(
            self.home / ".claude" / "projects" / "-ws" / "sig.jsonl",
            [
                {"type": "user", "timestamp": self.now, "message": {"role": "user", "content": "first prompt"}},
                {"type": "assistant", "requestId": "r1", "message": {"model": "m", "usage": usage}},
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "second prompt\n\n### User correction signal: unverified-claim\nreads as a correction.",
                            },
                            {"type": "text", "text": "[SOP REINFORCEMENT — verified excerpt]"},
                        ],
                    },
                },
                {"type": "assistant", "requestId": "r2", "message": {"model": "m", "usage": usage}},
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "content": "quoted [SOP REINFORCEMENT and ### User correction signal in output",
                            }
                        ],
                    },
                },
            ],
        )
        (session,) = self.core.read_claude(0)
        self.assertEqual((session.prompts, session.corrections, session.reinforcements), (2, 1, 1))
        text = self.core.render([session], "session", 7, 40, ["claude"], signals=True)
        self.assertIn("corrections", text)
        self.assertIn("SOP re-injections 1", text)

    def test_cache_misses_count_calls_that_lost_the_prompt_cache(self) -> None:
        def usage(fresh: int, read: int, write: int = 0) -> dict:
            return {
                "input_tokens": fresh,
                "cache_read_input_tokens": read,
                "cache_creation_input_tokens": write,
                "output_tokens": 1,
            }

        rows = [
            {"type": "assistant", "requestId": "r1", "message": {"model": "m", "usage": usage(50_000, 0, 0)}},
            {"type": "assistant", "requestId": "r2", "message": {"model": "m", "usage": usage(100, 50_000)}},
            {"type": "assistant", "requestId": "r3", "message": {"model": "m", "usage": usage(2, 50_100)}},
            # Cache lost (idle past its lifetime): everything is written again.
            {"type": "assistant", "requestId": "r4", "message": {"model": "m", "usage": usage(0, 0, 50_102)}},
            {"type": "assistant", "requestId": "r5", "message": {"model": "m", "usage": usage(3, 50_102)}},
        ]
        write_jsonl(self.home / ".claude" / "projects" / "-ws" / "miss.jsonl", rows)
        (session,) = self.core.read_claude(0)
        self.assertEqual(session.cache_misses, 1)
        text = self.core.render([session], "session", 7, 40, ["claude"], signals=True)
        self.assertIn("misses", text)
        self.assertIn("cache misses 1", text)
        self.assertNotIn("_prev_context", self.core.to_json([session]))

    def test_collect_groups_and_renders_without_prices(self) -> None:
        usage = {
            "input_tokens": 10,
            "cache_read_input_tokens": 90,
            "cache_creation_input_tokens": 0,
            "output_tokens": 5,
        }
        write_jsonl(
            self.home / ".claude" / "projects" / "-ws" / "a.jsonl",
            [{"type": "assistant", "timestamp": self.now, "requestId": "r", "message": {"model": "m", "usage": usage}}],
        )
        write_jsonl(
            self.home / ".claude" / "projects" / "-ws" / "b.jsonl",
            [{"type": "assistant", "timestamp": self.now, "requestId": "r", "message": {"model": "m", "usage": usage}}],
        )

        sessions = self.core.collect(365, ["claude"])
        self.assertEqual(len(sessions), 2)
        (row,) = self.core.group(sessions, "harness")
        self.assertEqual((row.calls, row.fresh_input, row.cache_read), (2, 20, 180))
        text = self.core.render([row], "harness", 365, 40, ["claude"])
        self.assertIn("hit", text)
        self.assertIn("90%", text)
        self.assertIn("no prices applied", text)
        self.assertNotIn("$", text)
        payload = json.loads(self.core.to_json([row]))
        self.assertEqual(payload["sessions"][0]["hit_rate"], 0.9)
        self.assertIn("cursor", payload["not_measured"])

    def test_SHOULD_count_subagent_transcripts_tagged_with_their_agent_type(self) -> None:
        """WHEN a session delegates, its subagents' calls live in <session>/subagents/ and must be counted."""
        usage = {
            "input_tokens": 1,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 0,
            "output_tokens": 1,
        }
        root = self.home / ".claude" / "projects" / "-ws"
        write_jsonl(
            root / "sess.jsonl",
            [{"type": "assistant", "requestId": "r0", "message": {"model": "claude-opus-5-5", "usage": usage}}],
        )
        child = root / "sess" / "subagents" / "agent-a1.jsonl"
        write_jsonl(
            child,
            [
                {"type": "user", "isSidechain": True, "message": {"role": "user", "content": "packet"}},
                {"type": "assistant", "requestId": "r1", "message": {"model": "claude-sonnet-5", "usage": usage}},
                {"type": "assistant", "requestId": "r2", "message": {"model": "claude-sonnet-5", "usage": usage}},
            ],
        )
        child.with_suffix(".meta.json").write_text(json.dumps({"agentType": "general-purpose"}))
        write_jsonl(
            root / "sess" / "subagents" / "agent-a2.jsonl",
            [{"type": "assistant", "requestId": "r3", "message": {"model": "claude-sonnet-5", "usage": usage}}],
        )

        sessions = self.core.read_claude(0)
        by_agent = {s.agent: (s.calls, s.prompts, s.cache_read) for s in sessions}
        self.assertEqual(by_agent, {"": (1, 0, 100), "general-purpose": (2, 0, 200), "subagent": (1, 0, 100)})
        rows = {row.session_id: row.calls for row in self.core.group(sessions, "agent")}
        self.assertEqual(
            rows,
            {
                "claude root claude-opus-5-5": 1,
                "claude general-purpose claude-sonnet-5": 2,
                "claude subagent claude-sonnet-5": 1,
            },
        )
        (total,) = self.core.group(sessions, "harness")
        self.assertEqual(total.calls, 4)

    def test_SHOULD_count_codex_pi_and_omp_subagents_tagged_by_role(self) -> None:
        """WHEN Codex, Pi or OMP delegate, child records must be counted and tagged, never read as roots."""
        total = {"input_tokens": 100, "cached_input_tokens": 90, "output_tokens": 5}
        count = {
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"last_token_usage": total, "total_token_usage": total}},
        }
        spawn = {"subagent": {"thread_spawn": {"parent_thread_id": "p1", "agent_role": "explorer"}}}
        day = self.home / ".codex" / "sessions" / "2026" / "09" / "06"
        write_jsonl(
            day / "rollout-root.jsonl", [{"type": "session_meta", "payload": {"id": "p1", "source": "cli"}}, count]
        )
        write_jsonl(
            day / "rollout-child.jsonl",
            [{"type": "session_meta", "payload": {"id": "c1", "source": spawn, "agent_role": "explorer"}}, count],
        )
        # Unit variants serialize as a bare string (codex protocol SubAgentSource::Review); `other` as an object.
        write_jsonl(
            day / "rollout-review.jsonl",
            [{"type": "session_meta", "payload": {"id": "r1", "source": {"subagent": "review"}}}, count],
        )
        write_jsonl(
            day / "rollout-guardian.jsonl",
            [{"type": "session_meta", "payload": {"id": "g1", "source": {"subagent": {"other": "guardian"}}}}, count],
        )
        self.assertEqual(
            {s.session_id: s.agent for s in self.core.read_codex(0)},
            {"p1": "", "c1": "explorer", "r1": "review", "g1": "guardian"},
        )

        usage = {"input": 10, "output": 1, "cacheRead": 90, "cacheWrite": 0}
        row = {"type": "message", "message": {"role": "assistant", "model": "m", "usage": usage}}
        pi = self.home / ".pi" / "agent" / "sessions" / "ws"
        write_jsonl(pi / "2026-09-06T10-00-00_root.jsonl", [row])
        # Child transcripts carry no row `type` (shape observed in ~/.pi subagent-artifacts, 2026-09-19).
        child = {"message": {"role": "assistant", "model": "m", "usage": usage}}
        user = {"message": {"role": "user", "usage": usage}}
        write_jsonl(
            pi / "subagent-artifacts" / "364c1e87-a035-43c5-bb74-3b06fb49a8d5_k-agent-reviewer_transcript.jsonl",
            [user, child],
        )
        write_jsonl(
            pi
            / "subagent-artifacts"
            / "9f246831-d353-45cd-955f-7d58c0c4f837_k-agent-claim-verifier_0_transcript.jsonl",
            [child],
        )
        # Run sessions duplicate a transcript's calls when one exists; untranscribed runs are counted once.
        run_row = {"type": "message", "message": {"role": "assistant", "model": "m", "usage": usage}}
        write_jsonl(
            pi / "2026-09-06T10-00-00_root" / "364c1e87-a035-43c5-bb74-3b06fb49a8d5" / "run-0" / "session.jsonl",
            [run_row],
        )
        info = {"type": "session_info", "name": "subagent-k-agent-smol-4152d2e9-2c96-4a50-a02d-9de119b27528-1"}
        write_jsonl(
            pi / "2026-09-06T10-00-00_root" / "34e1e654-b8a7-495c-acae-79220cd96f5a" / "run-0" / "session.jsonl",
            [info, run_row, run_row],
        )
        self.assertEqual(
            sorted((s.agent, s.calls) for s in self.core.read_pi(0)),
            [("", 1), ("k-agent-claim-verifier", 1), ("k-agent-reviewer", 1), ("k-agent-smol", 2)],
        )

        omp = self.home / ".omp" / "agent" / "sessions" / "ws"
        write_jsonl(omp / "2026-09-07T00-38-40_s1.jsonl", [row])
        write_jsonl(omp / "2026-09-07T00-38-40_s1" / "KbRecall.jsonl", [row, row])
        write_jsonl(omp / "2026-09-07T00-38-40_s1" / "KbRecall" / "__advisor.jsonl", [row])
        # The root session's own advisor sits beside its task children.
        write_jsonl(omp / "2026-09-07T00-38-40_s1" / "__advisor.jsonl", [row])
        sessions = self.core.read_omp(0)
        self.assertEqual(
            sorted((s.agent, s.calls) for s in sessions), [("", 1), ("advisor", 1), ("advisor", 1), ("subagent", 2)]
        )

    def test_SHOULD_price_anthropic_calls_by_billing_type_only_when_asked(self) -> None:
        """WHEN --cost is set, each call is priced at its own model's list rates with 5m/1h write multipliers."""
        priced = {
            "input_tokens": 10,
            "cache_read_input_tokens": 1_000_000,
            "cache_creation_input_tokens": 100_000,
            "cache_creation": {"ephemeral_5m_input_tokens": 60_000, "ephemeral_1h_input_tokens": 40_000},
            "output_tokens": 10_000,
        }
        zero = {"input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 0}
        write_jsonl(
            self.home / ".claude" / "projects" / "-ws" / "priced.jsonl",
            [
                {"type": "assistant", "requestId": "r1", "message": {"model": "claude-opus-5-5", "usage": priced}},
                {"type": "assistant", "requestId": "r2", "message": {"model": "<synthetic>", "usage": zero}},
            ],
        )
        write_jsonl(
            self.home / ".claude" / "projects" / "-ws" / "unpriced.jsonl",
            [{"type": "assistant", "requestId": "r1", "message": {"model": "claude-unknown", "usage": priced}}],
        )
        write_jsonl(
            self.home / ".claude" / "projects" / "-ws" / "dated.jsonl",
            [
                {
                    "type": "assistant",
                    "requestId": "r1",
                    "message": {"model": "claude-opus-5-5-20260101", "usage": priced},
                }
            ],
        )
        sessions = {s.session_id: s for s in self.core.read_claude(0)}
        session = sessions["priced"]
        # Opus 5.5 at $4 in / $20 out / $0.20 read: 10*4 + 1e6*0.2 + 60k*1.25*4 + 40k*2*4 + 10k*20.
        self.assertAlmostEqual(session.cost_usd, 1.02004)
        self.assertEqual((session.cache_write_1h, session.priced_calls, session.calls), (40_000, 2, 2))
        self.assertAlmostEqual(sessions.pop("dated").cost_usd, 1.02004)

        text = self.core.render(list(sessions.values()), "session", 7, 40, ["claude"], cost=True)
        self.assertIn("write 1h", text)
        self.assertIn("1.02", text)
        self.assertIn("n/a", text)
        self.assertIn("api $ 1.02", text)
        plain = self.core.render(list(sessions.values()), "session", 7, 40, ["claude"])
        self.assertNotIn("$", plain)
        # --signals drops the cost columns, so it drops the cost summary too.
        signals = self.core.render(list(sessions.values()), "session", 7, 40, ["claude"], signals=True, cost=True)
        self.assertNotIn("$", signals)

    def test_launcher_and_completion_cover_every_flag(self) -> None:
        launcher = LAUNCHER.read_text()
        self.assertIn('lib="$HOME/lib/,ai-usage/main.py"', launcher)
        completion = COMPLETION.read_text()
        parser = self.core.build_parser()
        flags = {action.option_strings[-1] for action in parser._actions if action.option_strings}
        for flag in flags - {"--help"}:
            self.assertIn(f"-l {flag[2:]}", completion, flag)
        for name in self.core.READERS:
            self.assertIn(name, completion)


if __name__ == "__main__":
    unittest.main()
