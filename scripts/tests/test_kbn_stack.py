#!/usr/bin/env python3
"""Focused tests for kbn stack."""

from __future__ import annotations

import unittest

try:
    from . import bin_command_support as _support
except ImportError:  # direct execution from scripts/tests
    import bin_command_support as _support

globals().update({name: value for name, value in vars(_support).items() if not name.startswith("__")})


class TestKbnStackCommand(unittest.TestCase):
    """WHEN tracking ,kbn-stack registry ownership."""

    def test_infers_legacy_ownership_safely(self):
        kbn_stack = _load_kbn_stack_command()

        assert kbn_stack.stack_started_by({"started_by": kbn_stack.STARTED_BY_AGENT}) == kbn_stack.STARTED_BY_AGENT
        assert kbn_stack.stack_started_by({"started_by": kbn_stack.STARTED_BY_USER}) == kbn_stack.STARTED_BY_USER
        assert kbn_stack.stack_started_by({"start_mode": "agent-detach"}) == kbn_stack.STARTED_BY_AGENT
        assert kbn_stack.stack_started_by({"kbn_pid": 1234}) == kbn_stack.STARTED_BY_AGENT
        assert kbn_stack.stack_started_by({"es_pid": "1234"}) == kbn_stack.STARTED_BY_USER
        assert kbn_stack.stack_started_by({"backend": "serverless"}) == kbn_stack.STARTED_BY_USER

    def test_records_start_mode_from_detach_or_tmux_context(self):
        kbn_stack = _load_kbn_stack_command()

        assert kbn_stack.start_mode(kbn_stack.parse_args(["--detach"]), None) == "agent-detach"
        assert kbn_stack.start_mode(kbn_stack.parse_args([]), "%1") == "interactive-tmux"
        assert kbn_stack.start_mode(kbn_stack.parse_args([]), None) == "manual-command"

    def test_status_state_uses_recorded_readiness_and_live_evidence(self):
        kbn_stack = _load_kbn_stack_command()
        cases = (
            (True, True, (True, True), "ready"),
            (True, False, (True, True), "ready"),
            (False, True, (False, False), "starting"),
            (False, True, (False, True), "starting"),
            (True, True, (False, True), "degraded"),
            (True, True, (True, False), "degraded"),
            (False, False, (True, True), "degraded"),
            (False, False, (False, False), "stale"),
        )
        for ready, process_alive, liveness, expected in cases:
            with self.subTest(ready=ready, process_alive=process_alive, liveness=liveness):
                entry = {"ready": ready}
                assert kbn_stack.status_state(entry, process_alive, *liveness) == expected

    def test_status_lists_registered_stacks_in_slot_order(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/B": {
                "slot": 2,
                "backend": "serverless",
                "branch": "feature/b",
                "started_by": kbn_stack.STARTED_BY_AGENT,
                "ready": False,
            },
            "/wt/A": {
                "slot": 0,
                "backend": "snapshot",
                "branch": "main",
                "started_by": kbn_stack.STARTED_BY_USER,
                "ready": True,
            },
        }
        with mock.patch.object(kbn_stack, "status_state", side_effect=["ready", "starting"]):
            with mock.patch.object(kbn_stack, "slot_liveness", side_effect=[(True, True), (False, True)]):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.run_status(registry) == 0

        lines = output.getvalue().splitlines()
        assert lines[0].split() == ["STATE", "SLOT", "BACKEND", "OWNER", "KIBANA", "ES", "BRANCH", "WORKTREE"]
        assert lines[1].split() == ["ready", "0", "snapshot", "user", "up", "up", "main", "/wt/A"]
        assert lines[2].split() == ["starting", "2", "serverless", "agent", "down", "up", "feature/b", "/wt/B"]

    def test_status_does_not_require_a_kibana_worktree(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack, "load_registry", return_value={}) as load_registry:
            with mock.patch.object(kbn_stack, "run_status", return_value=0) as run_status:
                with mock.patch.object(
                    kbn_stack, "resolve_worktree", side_effect=AssertionError("unexpected worktree lookup")
                ):
                    assert kbn_stack.main(["--status"]) == 0

        load_registry.assert_called_once_with()
        run_status.assert_called_once_with({})

    def test_prune_removes_only_fully_stale_entries(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/ready": {"slot": 0, "backend": "snapshot", "ready": True},
            "/starting": {"slot": 1, "backend": "snapshot", "ready": False, "started_by_pid": 1234},
            "/degraded": {"slot": 2, "backend": "snapshot", "ready": True},
            "/stale": {"slot": 3, "backend": "snapshot", "ready": True},
        }
        alive_slots = {0: (True, True), 1: (False, False), 2: (False, True), 3: (False, False)}
        with mock.patch.object(kbn_stack, "pid_alive", side_effect=lambda pid: pid == 1234):
            with _patched_ports(kbn_stack, alive_slots=alive_slots) as state:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.run_prune(registry) == 0

        assert set(registry) == {"/ready", "/starting", "/degraded"}
        assert set(state["saved"][-1]) == {"/ready", "/starting", "/degraded"}
        assert state["killed"] == []
        assert "/stale" in output.getvalue()

    def test_prune_does_not_require_a_kibana_worktree(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack, "load_registry", return_value={}) as load_registry:
            with mock.patch.object(kbn_stack, "run_prune", return_value=0) as run_prune:
                with mock.patch.object(
                    kbn_stack, "resolve_worktree", side_effect=AssertionError("unexpected worktree lookup")
                ):
                    assert kbn_stack.main(["--prune"]) == 0

        load_registry.assert_called_once_with()
        run_prune.assert_called_once_with({})

    def test_prune_may_ignore_the_exiting_launcher_pid(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/stale": {"slot": 0, "started_by_pid": 1234}}
        with mock.patch.object(kbn_stack, "pid_alive", side_effect=lambda pid: pid == 1234):
            with _patched_ports(kbn_stack, alive_slots={0: (False, False)}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    assert kbn_stack.run_prune(registry, ignored_pid=1234) == 0

        assert registry == {}
        assert state["saved"][-1] == {}

    def test_when_trigger_precedes_detached_reader_should_detect_it(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(f"{kbn_stack.TRIGGER_STRING}\n", encoding="utf-8")
            with mock.patch.object(kbn_stack.time, "monotonic", side_effect=[0.0, 0.0, 2.0]):
                with mock.patch.object(kbn_stack.time, "sleep"):
                    detected = kbn_stack.wait_for_trigger(logfile, timeout=1)

        assert detected is True

    def test_when_trigger_follows_detached_reader_should_detect_it(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text("", encoding="utf-8")

            def write_trigger(_seconds):
                logfile.write_text(f"{kbn_stack.TRIGGER_STRING}\n", encoding="utf-8")

            with mock.patch.object(kbn_stack.time, "monotonic", side_effect=[0.0, 0.0, 0.0]):
                with mock.patch.object(kbn_stack.time, "sleep", side_effect=write_trigger):
                    detected = kbn_stack.wait_for_trigger(logfile, timeout=1)

        assert detected is True

    def test_when_trigger_precedes_interactive_reader_should_launch_kibana(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(f"{kbn_stack.TRIGGER_STRING}\n", encoding="utf-8")
            with mock.patch.object(kbn_stack, "ensure_trial_license") as ensure_trial:
                with mock.patch.object(kbn_stack.subprocess, "run") as run:
                    with mock.patch.object(kbn_stack, "kibana_ready", return_value=True):
                        with mock.patch.object(kbn_stack, "mark_ready") as mark_ready:
                            kbn_stack.start_kibana_on_trigger(
                                logfile,
                                "http://localhost:9200",
                                "yarn start",
                                "%2",
                                "/worktree",
                                "http://localhost:5601",
                            )

        ensure_trial.assert_called_once_with("http://localhost:9200")
        wrapped_command = shlex.join(
            [sys.executable, str(Path(kbn_stack.__file__).resolve()), "--run-with-prune", "yarn", "start"]
        )
        run.assert_called_once_with(
            ["tmux", "send-keys", "-t", "%2", wrapped_command, "C-m"],
            check=False,
        )
        mark_ready.assert_called_once_with("/worktree", True)

    def test_interrupted_kibana_wrapper_invokes_quiet_pruning(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/worktree": {"slot": 0}}
        with mock.patch.object(kbn_stack.subprocess, "run", side_effect=KeyboardInterrupt):
            with mock.patch.object(kbn_stack, "load_registry", return_value=registry):
                with mock.patch.object(kbn_stack, "run_prune") as run_prune:
                    assert kbn_stack.run_with_prune(["yarn", "start"]) == 130

        run_prune.assert_called_once_with(registry, quiet=True)

    def test_interrupted_foreground_es_invokes_quiet_pruning(self):
        kbn_stack = _load_kbn_stack_command()
        proc = mock.Mock()
        proc.stdout = mock.MagicMock()
        proc.stdout.__iter__.side_effect = KeyboardInterrupt
        registry = {"/worktree": {"slot": 0}}

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            with mock.patch.object(kbn_stack.subprocess, "Popen", return_value=proc):
                with mock.patch.object(kbn_stack, "load_registry", return_value=registry):
                    with mock.patch.object(kbn_stack, "run_prune") as run_prune:
                        with self.assertRaises(KeyboardInterrupt):
                            kbn_stack.run_foreground_es(["yarn", "es"], logfile)

        run_prune.assert_called_once_with(registry, ignored_pid=os.getpid(), quiet=True)

    def test_pid_alive_rejects_non_pid_values(self):
        kbn_stack = _load_kbn_stack_command()

        for value in (None, "123", 1.5, True, False, 0, -1, 1 << 100):
            with self.subTest(value=value):
                assert kbn_stack.pid_alive(value) is False

    def test_pid_alive_classifies_process_probe_results(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack.os, "kill", return_value=None):
            assert kbn_stack.pid_alive(1234) is True
        with mock.patch.object(kbn_stack.os, "kill", side_effect=ProcessLookupError):
            assert kbn_stack.pid_alive(1234) is False
        with mock.patch.object(kbn_stack.os, "kill", side_effect=PermissionError):
            assert kbn_stack.pid_alive(1234) is True

    def test_pid_alive_treats_zombie_as_dead(self):
        kbn_stack = _load_kbn_stack_command()
        child = os.fork()
        if child == 0:
            os._exit(0)
        try:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if kbn_stack.pid_is_zombie(child):
                    break
                time.sleep(0.02)
            else:
                self.fail("child did not become a zombie")
            assert kbn_stack.pid_alive(child) is False
        finally:
            os.waitpid(child, 0)

    def test_ensure_ports_free_names_the_squatting_pid(self):
        kbn_stack = _load_kbn_stack_command()
        cfg = kbn_stack.derive(0)
        cfg["slot"] = 0

        with mock.patch.object(
            kbn_stack, "port_listener_pids", lambda port: [49880] if port == cfg["kbn_port"] else []
        ):
            with mock.patch.object(kbn_stack, "describe_pid", lambda pid: "node scripts/kibana --dev"):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    with self.assertRaises(SystemExit):
                        kbn_stack.ensure_ports_free(cfg)
        message = err.getvalue()
        assert "already in use" in message
        assert "49880" in message
        assert "node scripts/kibana --dev" in message

    def test_ensure_ports_free_passes_when_ports_are_free(self):
        kbn_stack = _load_kbn_stack_command()
        cfg = kbn_stack.derive(0)
        cfg["slot"] = 0

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: []):
            kbn_stack.ensure_ports_free(cfg)

    def test_listener_identity_accepts_own_process_group_and_descendants(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: [222]):
            with mock.patch.object(kbn_stack.os, "getpgid", lambda pid: 111):
                ok, listeners = kbn_stack.listener_identity_ok(5601, 111)
        assert ok is True
        assert listeners == [222]

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: [333]):
            with mock.patch.object(kbn_stack.os, "getpgid", lambda pid: {111: 111, 333: 999}[pid]):
                with mock.patch.object(kbn_stack, "pid_ancestors", lambda pid: {111, 1}):
                    ok, _ = kbn_stack.listener_identity_ok(5601, 111)
        assert ok is True

    def test_listener_identity_rejects_foreign_squatter(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: [49880]):
            with mock.patch.object(kbn_stack.os, "getpgid", lambda pid: {111: 111, 49880: 777}[pid]):
                with mock.patch.object(kbn_stack, "pid_ancestors", lambda pid: {777, 1}):
                    ok, listeners = kbn_stack.listener_identity_ok(5601, 111)
        assert ok is False
        assert listeners == [49880]

        with mock.patch.object(kbn_stack, "port_listener_pids", lambda port: []):
            ok, listeners = kbn_stack.listener_identity_ok(5601, 111)
        assert ok is False
        assert listeners == []

    def test_agent_start_does_not_stop_user_owned_serverless(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/user": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.STARTED_BY_USER,
            }
        }
        blocked, stopped, saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.STARTED_BY_AGENT,
        )

        assert blocked is True
        assert stopped == []
        assert "/user" in registry
        assert saved == []

    def test_agent_start_does_not_stop_any_serverless_when_user_owned_serverless_blocks(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/agent": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.STARTED_BY_AGENT,
            },
            "/user": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.STARTED_BY_USER,
            },
        }
        blocked, stopped, saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.STARTED_BY_AGENT,
        )

        assert blocked is True
        assert stopped == []
        assert set(registry) == {"/agent", "/user"}
        assert saved == []

    def test_agent_start_may_replace_agent_owned_serverless(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/agent": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.STARTED_BY_AGENT,
            }
        }
        blocked, stopped, _saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.STARTED_BY_AGENT,
        )

        assert blocked is False
        assert stopped == [("/agent", False)]
        assert registry == {}

    def test_stop_entry_respects_user_owned_guard(self):
        kbn_stack = _load_kbn_stack_command()
        calls: list[str | tuple[str, int]] = []
        entry = {
            "backend": "serverless",
            "slot": 0,
            "started_by": kbn_stack.STARTED_BY_USER,
        }
        original_docker_kill_serverless = kbn_stack.docker_kill_serverless
        original_kill_pid_group = kbn_stack.kill_pid_group

        kbn_stack.docker_kill_serverless = lambda: calls.append("docker")
        kbn_stack.kill_pid_group = lambda pid: calls.append(("pid", pid))
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                assert kbn_stack.stop_entry("/user", entry, allow_user_owned=False) is False
            assert calls == []

            with contextlib.redirect_stdout(io.StringIO()):
                assert kbn_stack.stop_entry("/user", entry, allow_user_owned=True) is True
            assert calls == ["docker"]
        finally:
            kbn_stack.docker_kill_serverless = original_docker_kill_serverless
            kbn_stack.kill_pid_group = original_kill_pid_group

    def test_reclaim_dead_slots_frees_both_dead_snapshot_slot(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            "/wt/B": {"slot": 1, "backend": "snapshot"},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

        assert changed is True
        assert "/wt/B" not in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_keeps_slot_while_any_recorded_process_is_alive(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack, "pid_alive", side_effect=lambda pid: pid == 1234):
            for key in ("started_by_pid", "kbn_pid", "es_pid"):
                for liveness in ((False, False), (False, True)):
                    with self.subTest(key=key, liveness=liveness):
                        registry = {
                            "/wt/A": {"slot": 0, "backend": "snapshot"},
                            "/wt/B": {"slot": 1, "backend": "snapshot", key: 1234},
                        }
                        with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: liveness}) as state:
                            with contextlib.redirect_stdout(io.StringIO()):
                                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                                slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

                        assert changed is False
                        assert "/wt/B" in registry
                        assert state["killed"] == []
                        assert slot == 2

    def test_reclaim_dead_recorded_process_still_frees_slot(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            "/wt/B": {"slot": 1, "backend": "snapshot", "started_by_pid": 1234},
        }
        with mock.patch.object(kbn_stack, "pid_alive", return_value=False):
            with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: (False, False)}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                    slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

        assert changed is True
        assert "/wt/B" not in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_kills_surviving_half_when_pair_split(self):
        kbn_stack = _load_kbn_stack_command()
        kbn_port, es_http = kbn_stack.derive(1)["kbn_port"], kbn_stack.derive(1)["es_http"]
        for alive, dead_survivor in (((False, True), es_http), ((True, False), kbn_port)):
            registry = {
                "/wt/A": {"slot": 0, "backend": "snapshot"},
                "/wt/B": {"slot": 1, "backend": "snapshot"},
            }
            with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: alive}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                    slot = kbn_stack.allocate_slot(registry, "/wt/C", None)
            assert state["killed"] == [dead_survivor], alive
            assert "/wt/B" not in registry
            assert slot == 1

    def test_reclaim_keeps_both_alive_slot_and_climbs(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            "/wt/B": {"slot": 1, "backend": "snapshot"},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

        assert changed is False
        assert "/wt/B" in registry
        assert state["killed"] == []
        assert slot == 2

    def test_reclaim_never_touches_serverless_entry(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/S": {"slot": 0, "backend": "serverless"}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.allocate_slot(registry, "/wt/C", None)

        assert changed is False
        assert "/wt/S" in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_leaves_current_worktree_sticky(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot"}}
        with _patched_ports(kbn_stack, alive_slots={1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.reclaim_dead_slots(registry, "/wt/B")
                slot = kbn_stack.allocate_slot(registry, "/wt/B", None)

        assert changed is False
        assert "/wt/B" in registry
        assert state["killed"] == []
        assert slot == 1

    def test_run_stop_reclaims_interactive_stack_by_port(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.STARTED_BY_USER}}
        kbn_port, es_http = kbn_stack.derive(1)["kbn_port"], kbn_stack.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_run_stop_drops_stale_entry_when_nothing_listens(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.STARTED_BY_USER}}
        with _patched_ports(kbn_stack, alive_slots={1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert state["killed"] == []

    def test_run_stop_all_reclaims_pidless_interactive_entry(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.STARTED_BY_USER}}
        kbn_port, es_http = kbn_stack.derive(1)["kbn_port"], kbn_stack.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.run_stop_all(registry)

        assert rc == 0
        assert state["saved"][-1] == {}
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_run_stop_reclaims_ports_even_when_recorded_pids_exist(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/B": {
                "slot": 1,
                "backend": "snapshot",
                "started_by": kbn_stack.STARTED_BY_AGENT,
                "kbn_pid": 4242,
                "es_pid": 4243,
            }
        }
        kbn_port, es_http = kbn_stack.derive(1)["kbn_port"], kbn_stack.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with mock.patch.object(kbn_stack, "kill_pid_group") as kill_group:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = kbn_stack.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert kill_group.mock_calls == [mock.call(4242), mock.call(4243)]
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_kill_port_listeners_reaps_hang_after_unbind_process_group(self):
        kbn_stack = _load_kbn_stack_command()
        kbn_stack.KILL_GRACE_SECONDS = 0.2
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hang_server.py"
            script.write_text(_HANG_AFTER_UNBIND_SERVER)
            port, pgid, members = _spawn_hang_after_unbind_group(script)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    acted = kbn_stack.kill_port_listeners(port)
                live = [pid for pid in members if kbn_stack.pid_alive(pid)]
                assert acted is True
                assert kbn_stack.port_listener_pids(port) == []
                assert live == [], live
            finally:
                _reap_group(pgid, leader=pgid)

    def test_snapshot_es_command_pins_merge_disk_watermark_before_user_flags(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["-E", "node.attr.foo=bar"])
        cfg = kbn_stack.derive(0)
        cfg["slot"] = 0
        cmd = kbn_stack.es_command(args, cfg, Path("/tmp/es-data"))
        settings = _es_dash_e_settings(cmd)
        assert "indices.merge.disk.watermark.high=2gb" in settings
        assert settings.index("indices.merge.disk.watermark.high=2gb") < settings.index("node.attr.foo=bar")

    def test_snapshot_es_command_lets_later_user_flag_override_merge_disk_watermark(self):
        kbn_stack = _load_kbn_stack_command()
        override = "indices.merge.disk.watermark.high=99%"
        args = kbn_stack.parse_args(["-E", override])
        cfg = kbn_stack.derive(0)
        cfg["slot"] = 0
        cmd = kbn_stack.es_command(args, cfg, Path("/tmp/es-data"))
        settings = _es_dash_e_settings(cmd)
        assert settings.count("indices.merge.disk.watermark.high=2gb") == 1
        assert settings.index("indices.merge.disk.watermark.high=2gb") < settings.index(override)

    def test_default_groups_platform_injects_allowlist_on_yarn_start(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args([])
        assert args.plugin_groups == ("platform",)
        assert args.es_heap == "1g"
        cmd = kbn_stack.kibana_command(args, kbn_stack.derive(0))
        assert "--plugins.allowlistPluginGroups.0=platform" in cmd
        assert "--plugins.allowlistPluginGroups.1=" not in cmd

    def test_groups_all_omits_allowlist(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["--groups", "all"])
        assert args.plugin_groups == ()
        cmd = kbn_stack.kibana_command(args, kbn_stack.derive(0))
        assert "allowlistPluginGroups" not in cmd

    def test_groups_comma_list_indexes_from_zero(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["--groups", "platform,security"])
        flags = kbn_stack.resolved_kbn_flags(args)
        assert flags[:2] == [
            "plugins.allowlistPluginGroups.0=platform",
            "plugins.allowlistPluginGroups.1=security",
        ]

    def test_explicit_k_allowlist_skips_group_injection(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["-K", "plugins.allowlistPluginGroups.0=security"])
        assert kbn_stack.resolved_kbn_flags(args) == ["plugins.allowlistPluginGroups.0=security"]

    def test_unknown_group_exits(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.parse_args(["--groups", "nope"])

    def test_groups_all_cannot_mix_with_named_groups(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.parse_args(["--groups", "all,platform"])

    def test_es_java_opts_sets_xms_xmx_and_keeps_other_tokens(self):
        kbn_stack = _load_kbn_stack_command()
        assert kbn_stack.es_java_opts("1g") == "-Xms1g -Xmx1g"
        assert kbn_stack.es_java_opts("512m", "-Xms1536m -Xmx1536m -XX:+UseG1GC") == "-Xms512m -Xmx512m -XX:+UseG1GC"

    def test_serverless_rejects_custom_es_heap(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.parse_args(["--es", "serverless", "--es-heap", "512m"])

    def test_serverless_allows_default_es_heap(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.parse_args(["--es", "serverless"])
        assert args.es_heap == "1g"

    def test_invalid_es_heap_exits(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.parse_args(["--es-heap", "1"])


if __name__ == "__main__":
    unittest.main()
