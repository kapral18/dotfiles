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

        assert (
            kbn_stack.store.stack_started_by({"started_by": kbn_stack.config.STARTED_BY_AGENT})
            == kbn_stack.config.STARTED_BY_AGENT
        )
        assert (
            kbn_stack.store.stack_started_by({"started_by": kbn_stack.config.STARTED_BY_USER})
            == kbn_stack.config.STARTED_BY_USER
        )
        assert kbn_stack.store.stack_started_by({"start_mode": "agent-detach"}) == kbn_stack.config.STARTED_BY_AGENT
        assert kbn_stack.store.stack_started_by({"kbn_pid": 1234}) == kbn_stack.config.STARTED_BY_AGENT
        assert kbn_stack.store.stack_started_by({"es_pid": "1234"}) == kbn_stack.config.STARTED_BY_USER
        assert kbn_stack.store.stack_started_by({"backend": "serverless"}) == kbn_stack.config.STARTED_BY_USER

    def test_records_start_mode_from_detach_or_tmux_context(self):
        kbn_stack = _load_kbn_stack_command()

        assert kbn_stack.cli.start_mode(kbn_stack.cli.parse_args(["--detach"]), None) == "agent-detach"
        assert kbn_stack.cli.start_mode(kbn_stack.cli.parse_args([]), "%1") == "interactive-tmux"
        assert kbn_stack.cli.start_mode(kbn_stack.cli.parse_args([]), None) == "manual-command"

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
                assert kbn_stack.liveness.status_state(entry, process_alive, *liveness) == expected

    def test_status_lists_registered_stacks_in_slot_order(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/B": {
                "slot": 2,
                "backend": "serverless",
                "branch": "feature/b",
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
                "ready": False,
            },
            "/wt/A": {
                "slot": 0,
                "backend": "snapshot",
                "branch": "main",
                "started_by": kbn_stack.config.STARTED_BY_USER,
                "ready": True,
            },
        }
        with mock.patch.object(kbn_stack.liveness, "status_state", side_effect=["ready", "starting"]):
            with mock.patch.object(kbn_stack.liveness, "slot_liveness", side_effect=[(True, True), (False, True)]):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.lifecycle.run_status(registry) == 0

        lines = output.getvalue().splitlines()
        assert lines[0].split() == ["STATE", "SLOT", "BACKEND", "OWNER", "KIBANA", "ES", "BRANCH", "WORKTREE"]
        assert lines[1].split() == ["ready", "0", "snapshot", "user", "up", "up", "main", "/wt/A"]
        assert lines[2].split() == ["starting", "2", "serverless", "agent", "down", "up", "feature/b", "/wt/B"]

    def test_status_does_not_require_a_kibana_worktree(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack.store, "load_registry", return_value={}) as load_registry:
            with mock.patch.object(kbn_stack.lifecycle, "run_status", return_value=0) as run_status:
                with mock.patch.object(
                    kbn_stack.checkout, "resolve_worktree", side_effect=AssertionError("unexpected worktree lookup")
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
        with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 1234):
            with _patched_ports(kbn_stack, alive_slots=alive_slots) as state:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.lifecycle.run_prune(registry) == 0

        assert set(registry) == {"/ready", "/starting", "/degraded"}
        assert set(state["saved"][-1]) == {"/ready", "/starting", "/degraded"}
        assert state["killed"] == []
        assert "/stale" in output.getvalue()

    def test_prune_does_not_require_a_kibana_worktree(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack.store, "load_registry", return_value={}) as load_registry:
            with mock.patch.object(kbn_stack.lifecycle, "run_prune", return_value=0) as run_prune:
                with mock.patch.object(
                    kbn_stack.checkout, "resolve_worktree", side_effect=AssertionError("unexpected worktree lookup")
                ):
                    assert kbn_stack.main(["--prune"]) == 0

        load_registry.assert_called_once_with()
        run_prune.assert_called_once_with({})

    def test_prune_may_ignore_the_exiting_launcher_pid(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/stale": {"slot": 0, "started_by_pid": 1234}}
        with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 1234):
            with _patched_ports(kbn_stack, alive_slots={0: (False, False)}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    assert kbn_stack.lifecycle.run_prune(registry, ignored_pid=1234) == 0

        assert registry == {}
        assert state["saved"][-1] == {}

    def test_when_serverless_logs_security_index_ready_should_finish_waiting(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(" info [runServerlessCluster] Security index ready (21.5s)\n")
            verdict = kbn_stack.es_log.wait_for_trigger(
                logfile, timeout=1, trigger=kbn_stack.config.SERVERLESS_TRIGGER_STRING
            )
            assert verdict == kbn_stack.config.WAIT_TRIGGER

    def test_when_trigger_precedes_detached_reader_should_detect_it(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(f"{kbn_stack.config.TRIGGER_STRING}\n", encoding="utf-8")
            with mock.patch.object(kbn_stack.es_log.time, "monotonic", side_effect=[0.0, 0.0, 2.0]):
                with mock.patch.object(kbn_stack.es_log.time, "sleep"):
                    detected = kbn_stack.es_log.wait_for_trigger(logfile, timeout=1)

        assert detected == kbn_stack.config.WAIT_TRIGGER

    def test_when_trigger_follows_detached_reader_should_detect_it(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text("", encoding="utf-8")

            def write_trigger(_seconds):
                logfile.write_text(f"{kbn_stack.config.TRIGGER_STRING}\n", encoding="utf-8")

            with mock.patch.object(kbn_stack.es_log.time, "monotonic", side_effect=[0.0, 0.0, 0.0]):
                with mock.patch.object(kbn_stack.es_log.time, "sleep", side_effect=write_trigger):
                    detected = kbn_stack.es_log.wait_for_trigger(logfile, timeout=1)

        assert detected == kbn_stack.config.WAIT_TRIGGER

    def test_when_trigger_precedes_interactive_reader_should_launch_kibana(self):
        kbn_stack = _load_kbn_stack_command()

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(f"{kbn_stack.config.TRIGGER_STRING}\n", encoding="utf-8")
            with mock.patch.object(kbn_stack.trial_license, "ensure_trial_license") as ensure_trial:
                with mock.patch.object(kbn_stack.launch.subprocess, "run") as run:
                    with mock.patch.object(kbn_stack.launch, "kibana_ready", return_value=True):
                        with mock.patch.object(kbn_stack.store, "mark_ready") as mark_ready:
                            kbn_stack.launch.start_kibana_on_trigger(
                                logfile,
                                "http://localhost:9200",
                                "yarn start",
                                "%2",
                                "/worktree",
                                "http://localhost:5601",
                                "snapshot",
                                Path(tmp) / "data",
                            )

        ensure_trial.assert_called_once_with("http://localhost:9200", Path(tmp) / "data")
        wrapped_command = shlex.join(
            [
                "env",
                "KBN_STACK_WORKTREE=/worktree",
                sys.executable,
                str(Path(kbn_stack.__file__).resolve()),
                "--run-with-prune",
                "yarn",
                "start",
            ]
        )
        run.assert_called_once_with(
            ["tmux", "send-keys", "-t", "%2", wrapped_command, "C-m"],
            check=False,
        )
        mark_ready.assert_called_once_with("/worktree", True)

    def test_interrupted_kibana_wrapper_invokes_quiet_pruning(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/worktree": {"slot": 0}}
        with mock.patch.object(kbn_stack.lifecycle.subprocess, "run", side_effect=KeyboardInterrupt):
            with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                with mock.patch.object(kbn_stack.lifecycle, "run_prune") as run_prune:
                    assert kbn_stack.lifecycle.run_with_prune(["yarn", "start"]) == 130

        run_prune.assert_called_once_with(registry, quiet=True)

    def test_kibana_wrapper_records_itself_as_the_entry_kbn_pid(self):
        kbn_stack = _load_kbn_stack_command()
        # The wrapper outlives dev-mode server restarts, so its pid keeps the worktree
        # a shared-ES client while Kibana's port is unbound.
        with (
            mock.patch.dict(os.environ, {"KBN_STACK_WORKTREE": "/worktree"}),
            mock.patch.object(kbn_stack.lifecycle.subprocess, "run", return_value=mock.Mock(returncode=0)),
            mock.patch.object(kbn_stack.store, "update_worktree_entry") as update,
            mock.patch.object(kbn_stack.store, "load_registry", return_value={}),
            mock.patch.object(kbn_stack.lifecycle, "run_prune"),
        ):
            assert kbn_stack.lifecycle.run_with_prune(["yarn", "start"]) == 0
        update.assert_called_once_with("/worktree", kbn_pid=os.getpid())

    def test_interrupted_foreground_es_invokes_quiet_pruning(self):
        kbn_stack = _load_kbn_stack_command()
        proc = mock.Mock()
        proc.stdout = mock.MagicMock()
        proc.stdout.__iter__.side_effect = KeyboardInterrupt
        registry = {"/worktree": {"slot": 0}}

        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            with mock.patch.object(kbn_stack.launch.subprocess, "Popen", return_value=proc):
                with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                    with mock.patch.object(kbn_stack.lifecycle, "run_prune") as run_prune:
                        with self.assertRaises(KeyboardInterrupt):
                            kbn_stack.launch.run_foreground_es(["yarn", "es"], logfile)

        run_prune.assert_called_once_with(registry, ignored_pid=os.getpid(), quiet=True)

    def test_pid_alive_rejects_non_pid_values(self):
        kbn_stack = _load_kbn_stack_command()

        for value in (None, "123", 1.5, True, False, 0, -1, 1 << 100):
            with self.subTest(value=value):
                assert kbn_stack.procs.pid_alive(value) is False

    def test_pid_alive_classifies_process_probe_results(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack.procs.os, "kill", return_value=None):
            assert kbn_stack.procs.pid_alive(1234) is True
        with mock.patch.object(kbn_stack.procs.os, "kill", side_effect=ProcessLookupError):
            assert kbn_stack.procs.pid_alive(1234) is False
        with mock.patch.object(kbn_stack.procs.os, "kill", side_effect=PermissionError):
            assert kbn_stack.procs.pid_alive(1234) is True

    def test_pid_alive_treats_zombie_as_dead(self):
        kbn_stack = _load_kbn_stack_command()
        child = os.fork()
        if child == 0:
            os._exit(0)
        try:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if kbn_stack.procs.pid_is_zombie(child):
                    break
                time.sleep(0.02)
            else:
                self.fail("child did not become a zombie")
            assert kbn_stack.procs.pid_alive(child) is False
        finally:
            os.waitpid(child, 0)

    def test_ensure_ports_free_names_the_squatting_pid(self):
        kbn_stack = _load_kbn_stack_command()
        cfg = kbn_stack.slots.derive(0)
        cfg["slot"] = 0

        with mock.patch.object(
            kbn_stack.procs, "port_listener_pids", lambda port: [49880] if port == cfg["kbn_port"] else []
        ):
            with mock.patch.object(kbn_stack.procs, "describe_pid", lambda pid: "node scripts/kibana --dev"):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    with self.assertRaises(SystemExit):
                        kbn_stack.liveness.ensure_ports_free(cfg)
        message = err.getvalue()
        assert "already in use" in message
        assert "49880" in message
        assert "node scripts/kibana --dev" in message

    def test_ensure_ports_free_passes_when_ports_are_free(self):
        kbn_stack = _load_kbn_stack_command()
        cfg = kbn_stack.slots.derive(0)
        cfg["slot"] = 0

        with mock.patch.object(kbn_stack.procs, "port_listener_pids", lambda port: []):
            kbn_stack.liveness.ensure_ports_free(cfg)

    def test_listener_identity_accepts_own_process_group_and_descendants(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack.procs, "port_listener_pids", lambda port: [222]):
            with mock.patch.object(kbn_stack.procs.os, "getpgid", lambda pid: 111):
                ok, listeners = kbn_stack.procs.listener_identity_ok(5601, 111)
        assert ok is True
        assert listeners == [222]

        with mock.patch.object(kbn_stack.procs, "port_listener_pids", lambda port: [333]):
            with mock.patch.object(kbn_stack.procs.os, "getpgid", lambda pid: {111: 111, 333: 999}[pid]):
                with mock.patch.object(kbn_stack.procs, "pid_ancestors", lambda pid: {111, 1}):
                    ok, _ = kbn_stack.procs.listener_identity_ok(5601, 111)
        assert ok is True

    def test_listener_identity_rejects_foreign_squatter(self):
        kbn_stack = _load_kbn_stack_command()

        with mock.patch.object(kbn_stack.procs, "port_listener_pids", lambda port: [49880]):
            with mock.patch.object(kbn_stack.procs.os, "getpgid", lambda pid: {111: 111, 49880: 777}[pid]):
                with mock.patch.object(kbn_stack.procs, "pid_ancestors", lambda pid: {777, 1}):
                    ok, listeners = kbn_stack.procs.listener_identity_ok(5601, 111)
        assert ok is False
        assert listeners == [49880]

        with mock.patch.object(kbn_stack.procs, "port_listener_pids", lambda port: []):
            ok, listeners = kbn_stack.procs.listener_identity_ok(5601, 111)
        assert ok is False
        assert listeners == []

    def test_agent_start_does_not_stop_user_owned_serverless(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/user": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.config.STARTED_BY_USER,
            }
        }
        blocked, stopped, saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.config.STARTED_BY_AGENT,
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
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            },
            "/user": {
                "backend": "serverless",
                "slot": 0,
                "started_by": kbn_stack.config.STARTED_BY_USER,
            },
        }
        blocked, stopped, saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.config.STARTED_BY_AGENT,
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
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            }
        }
        blocked, stopped, _saved = _capture_stop_existing_serverless(
            kbn_stack,
            registry,
            kbn_stack.config.STARTED_BY_AGENT,
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
            "started_by": kbn_stack.config.STARTED_BY_USER,
        }
        original_docker_kill_serverless = kbn_stack.procs.docker_kill_serverless
        original_kill_pid_group = kbn_stack.procs.kill_pid_group

        kbn_stack.procs.docker_kill_serverless = lambda: calls.append("docker")
        kbn_stack.procs.kill_pid_group = lambda pid: calls.append(("pid", pid))
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                assert kbn_stack.lifecycle.stop_entry("/user", entry, allow_user_owned=False) is False
            assert calls == []

            with contextlib.redirect_stdout(io.StringIO()):
                assert kbn_stack.lifecycle.stop_entry("/user", entry, allow_user_owned=True) is True
            assert calls == ["docker"]
        finally:
            kbn_stack.procs.docker_kill_serverless = original_docker_kill_serverless
            kbn_stack.procs.kill_pid_group = original_kill_pid_group

    def test_reclaim_dead_slots_frees_both_dead_snapshot_slot(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            "/wt/B": {"slot": 1, "backend": "snapshot"},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.slots.allocate_slot(registry, "/wt/C", None)

        assert changed is True
        assert "/wt/B" not in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_keeps_slot_while_any_recorded_process_is_alive(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 1234):
            for key in ("started_by_pid", "kbn_pid", "es_pid"):
                for liveness in ((False, False), (False, True)):
                    with self.subTest(key=key, liveness=liveness):
                        registry = {
                            "/wt/A": {"slot": 0, "backend": "snapshot"},
                            "/wt/B": {"slot": 1, "backend": "snapshot", key: 1234},
                        }
                        with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: liveness}) as state:
                            with contextlib.redirect_stdout(io.StringIO()):
                                changed = kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/C")
                                slot = kbn_stack.slots.allocate_slot(registry, "/wt/C", None)

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
        with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
            with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: (False, False)}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    changed = kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/C")
                    slot = kbn_stack.slots.allocate_slot(registry, "/wt/C", None)

        assert changed is True
        assert "/wt/B" not in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_kills_surviving_half_when_pair_split(self):
        kbn_stack = _load_kbn_stack_command()
        kbn_port, es_http = kbn_stack.slots.derive(1)["kbn_port"], kbn_stack.slots.derive(1)["es_http"]
        for alive, dead_survivor in (((False, True), es_http), ((True, False), kbn_port)):
            registry = {
                "/wt/A": {"slot": 0, "backend": "snapshot"},
                "/wt/B": {"slot": 1, "backend": "snapshot"},
            }
            with _patched_ports(kbn_stack, alive_slots={0: (True, True), 1: alive}) as state:
                with contextlib.redirect_stdout(io.StringIO()):
                    kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/C")
                    slot = kbn_stack.slots.allocate_slot(registry, "/wt/C", None)
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
                changed = kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.slots.allocate_slot(registry, "/wt/C", None)

        assert changed is False
        assert "/wt/B" in registry
        assert state["killed"] == []
        assert slot == 2

    def test_reclaim_never_touches_serverless_entry(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/S": {"slot": 0, "backend": "serverless"}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/C")
                slot = kbn_stack.slots.allocate_slot(registry, "/wt/C", None)

        assert changed is False
        assert "/wt/S" in registry
        assert state["killed"] == []
        assert slot == 1

    def test_reclaim_leaves_current_worktree_sticky(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot"}}
        with _patched_ports(kbn_stack, alive_slots={1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/B")
                slot = kbn_stack.slots.allocate_slot(registry, "/wt/B", None)

        assert changed is False
        assert "/wt/B" in registry
        assert state["killed"] == []
        assert slot == 1

    def test_run_stop_reclaims_interactive_stack_by_port(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.config.STARTED_BY_USER}}
        kbn_port, es_http = kbn_stack.slots.derive(1)["kbn_port"], kbn_stack.slots.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.lifecycle.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_run_stop_drops_stale_entry_when_nothing_listens(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.config.STARTED_BY_USER}}
        with _patched_ports(kbn_stack, alive_slots={1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.lifecycle.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert state["killed"] == []

    def test_run_stop_all_reclaims_pidless_interactive_entry(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/B": {"slot": 1, "backend": "snapshot", "started_by": kbn_stack.config.STARTED_BY_USER}}
        kbn_port, es_http = kbn_stack.slots.derive(1)["kbn_port"], kbn_stack.slots.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.lifecycle.run_stop_all(registry)

        assert rc == 0
        assert state["saved"][-1] == {}
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_run_stop_reclaims_ports_even_when_recorded_pids_exist(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/B": {
                "slot": 1,
                "backend": "snapshot",
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
                "kbn_pid": 4242,
                "es_pid": 4243,
            }
        }
        kbn_port, es_http = kbn_stack.slots.derive(1)["kbn_port"], kbn_stack.slots.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with mock.patch.object(kbn_stack.procs, "kill_pid_group") as kill_group:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = kbn_stack.lifecycle.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert kill_group.mock_calls == [mock.call(4242), mock.call(4243)]
        assert set(state["killed"]) == {kbn_port, es_http}

    def test_kill_port_listeners_reaps_hang_after_unbind_process_group(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack.config, "KILL_GRACE_SECONDS", 0.2), tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hang_server.py"
            script.write_text(_HANG_AFTER_UNBIND_SERVER)
            port, pgid, members = _spawn_hang_after_unbind_group(script)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    acted = kbn_stack.procs.kill_port_listeners(port)
                live = [pid for pid in members if kbn_stack.procs.pid_alive(pid)]
                assert acted is True
                assert kbn_stack.procs.port_listener_pids(port) == []
                assert live == [], live
            finally:
                _reap_group(pgid, leader=pgid)

    def test_when_serverless_should_translate_es_project_type_and_preserve_kibana_type(self):
        kbn_stack = _load_kbn_stack_command()
        # Consumer contract: Kibana kbn-es/src/utils/docker.ts esProjectTypeFromKbn,
        # introduced for the CLI in elastic/kibana commit 5385f96a1321 (#245113).
        cases = (
            ([], "es", "elasticsearch_general_purpose"),
            (["--project-type", "es"], "es", "elasticsearch_general_purpose"),
            (["--project-type", "oblt"], "oblt", "observability"),
            (["--project-type", "security"], "security", "security"),
        )
        for flags, kibana_type, es_type in cases:
            with self.subTest(flags=flags):
                args = kbn_stack.cli.parse_args(["--es", "serverless", *flags])
                cfg = kbn_stack.slots.derive(0)
                self.assertEqual(
                    kbn_stack.launch.es_command(args, cfg, Path("/tmp/es-data"), "yarn"),
                    [
                        "yarn",
                        "es",
                        "serverless",
                        "--projectType",
                        es_type,
                        "--port",
                        "9200",
                        "--basePath",
                        "/tmp",
                        "--dataPath",
                        "es-data",
                        "--waitForReady",
                        "--kill",
                    ],
                )
                kibana_flags = shlex.split(kbn_stack.launch.kibana_command(args, cfg, "yarn"))
                self.assertEqual(
                    [flag for flag in kibana_flags if flag.startswith("--serverless=")],
                    [f"--serverless={kibana_type}"],
                )

    def test_when_serverless_stops_should_remove_es_and_uiam_containers(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack.procs.subprocess, "run") as run:
            kbn_stack.procs.docker_kill_serverless()
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [["docker", "rm", "-f", name] for name in ("es01", "es02", "uiam", "uiam-cosmosdb")],
        )

    def test_snapshot_es_command_pins_merge_disk_watermark_before_user_flags(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["-E", "node.attr.foo=bar"])
        cfg = kbn_stack.slots.derive(0)
        cfg["slot"] = 0
        cmd = kbn_stack.launch.es_command(args, cfg, Path("/tmp/es-data"), "yarn")
        settings = _es_dash_e_settings(cmd)
        assert "indices.merge.disk.watermark.high=2gb" in settings
        assert settings.index("indices.merge.disk.watermark.high=2gb") < settings.index("node.attr.foo=bar")

    def test_snapshot_es_command_lets_later_user_flag_override_merge_disk_watermark(self):
        kbn_stack = _load_kbn_stack_command()
        override = "indices.merge.disk.watermark.high=99%"
        args = kbn_stack.cli.parse_args(["-E", override])
        cfg = kbn_stack.slots.derive(0)
        cfg["slot"] = 0
        cmd = kbn_stack.launch.es_command(args, cfg, Path("/tmp/es-data"), "yarn")
        settings = _es_dash_e_settings(cmd)
        assert settings.count("indices.merge.disk.watermark.high=2gb") == 1
        assert settings.index("indices.merge.disk.watermark.high=2gb") < settings.index(override)

    def test_default_groups_platform_injects_allowlist_on_yarn_start(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args([])
        assert args.plugin_groups == ("platform",)
        assert args.es_heap == "1g"
        cmd = kbn_stack.launch.kibana_command(args, kbn_stack.slots.derive(0), "yarn")
        assert "--plugins.allowlistPluginGroups.0=platform" in cmd
        assert "--plugins.allowlistPluginGroups.1=" not in cmd

    def test_package_manager_follows_pnpm_lockfile(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            # Older Kibana branches: yarn.lock only.
            (Path(tmp) / "yarn.lock").write_text("", encoding="utf-8")
            assert kbn_stack.checkout.package_manager(tmp) == "yarn"
            # Kibana main after the pnpm migration keeps yarn.lock next to pnpm-lock.yaml.
            (Path(tmp) / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            assert kbn_stack.checkout.package_manager(tmp) == "pnpm"

    def test_commands_use_the_resolved_package_manager(self):
        kbn_stack = _load_kbn_stack_command()
        cfg = kbn_stack.slots.derive(0)
        cfg["slot"] = 0
        for pm in ("pnpm", "yarn"):
            with self.subTest(pm=pm):
                kbn = shlex.split(kbn_stack.launch.kibana_command(kbn_stack.cli.parse_args([]), cfg, pm))
                assert kbn[:2] == [pm, "start"]
                snapshot = kbn_stack.launch.es_command(kbn_stack.cli.parse_args([]), cfg, Path("/tmp/es-data"), pm)
                assert snapshot[:3] == [pm, "es", "snapshot"]
                serverless = kbn_stack.launch.es_command(
                    kbn_stack.cli.parse_args(["--es", "serverless"]), cfg, Path("/tmp/es-data"), pm
                )
                assert serverless[:3] == [pm, "es", "serverless"]

    def test_groups_all_omits_allowlist(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["--groups", "all"])
        assert args.plugin_groups == ()
        cmd = kbn_stack.launch.kibana_command(args, kbn_stack.slots.derive(0), "yarn")
        assert "allowlistPluginGroups" not in cmd

    def test_groups_comma_list_indexes_from_zero(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["--groups", "platform,security"])
        flags = kbn_stack.cli.resolved_kbn_flags(args)
        assert flags[:2] == [
            "plugins.allowlistPluginGroups.0=platform",
            "plugins.allowlistPluginGroups.1=security",
        ]

    def test_explicit_k_allowlist_skips_group_injection(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["-K", "plugins.allowlistPluginGroups.0=security"])
        assert kbn_stack.cli.resolved_kbn_flags(args) == ["plugins.allowlistPluginGroups.0=security"]

    def test_unknown_group_exits(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.cli.parse_args(["--groups", "nope"])

    def test_groups_all_cannot_mix_with_named_groups(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.cli.parse_args(["--groups", "all,platform"])

    def test_es_java_opts_sets_xms_xmx_and_keeps_other_tokens(self):
        kbn_stack = _load_kbn_stack_command()
        assert kbn_stack.cli.es_java_opts("1g") == "-Xms1g -Xmx1g"
        assert (
            kbn_stack.cli.es_java_opts("512m", "-Xms1536m -Xmx1536m -XX:+UseG1GC") == "-Xms512m -Xmx512m -XX:+UseG1GC"
        )

    def test_serverless_rejects_custom_es_heap(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.cli.parse_args(["--es", "serverless", "--es-heap", "512m"])

    def test_serverless_allows_default_es_heap(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["--es", "serverless"])
        assert args.es_heap == "1g"

    def test_invalid_es_heap_exits(self):
        kbn_stack = _load_kbn_stack_command()
        with self.assertRaises(SystemExit):
            kbn_stack.cli.parse_args(["--es-heap", "1"])


def _shared_instance(kbn_stack, slot: int, version: str = "9.6.0", **over) -> dict:
    """A registry `__es__` entry with every field the attach path dereferences."""
    cfg = kbn_stack.slots.derive(slot)
    instance = {
        "slot": slot,
        "es_url": cfg["es_url"],
        "es_http": cfg["es_http"],
        "es_transport": cfg["es_transport"],
        "data": f"shared-{version}",
        "log": f"/tmp/es-shared-{version}.log",
        "es_pid": 4242,
    }
    instance.update(over)
    return instance


class TestKbnStackSharedEs(unittest.TestCase):
    """WHEN sharing one snapshot ES across compatible worktrees."""

    def test_share_eligibility_requires_default_es_environment(self):
        kbn_stack = _load_kbn_stack_command()
        assert kbn_stack.cli.share_eligible(kbn_stack.cli.parse_args([])) is True
        # Kibana-side flags never affect ES sharing.
        assert kbn_stack.cli.share_eligible(kbn_stack.cli.parse_args(["-K", "foo=bar", "--groups", "all"])) is True
        assert kbn_stack.cli.share_eligible(kbn_stack.cli.parse_args(["--slot", "3"])) is True
        # Any ES-level override isolates.
        assert kbn_stack.cli.share_eligible(kbn_stack.cli.parse_args(["--isolated-es"])) is False
        assert kbn_stack.cli.share_eligible(kbn_stack.cli.parse_args(["-E", "foo=bar"])) is False
        assert kbn_stack.cli.share_eligible(kbn_stack.cli.parse_args(["--data", "mydata"])) is False
        assert kbn_stack.cli.share_eligible(kbn_stack.cli.parse_args(["--es-heap", "1536m"])) is False
        assert kbn_stack.cli.share_eligible(kbn_stack.cli.parse_args(["--es", "serverless"])) is False

    def test_read_worktree_version_resolves_package_json(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "package.json").write_text('{"version": "9.6.0"}', encoding="utf-8")
            assert kbn_stack.checkout.read_worktree_version(tmp) == "9.6.0"
        with tempfile.TemporaryDirectory() as tmp:
            assert kbn_stack.checkout.read_worktree_version(tmp) is None
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "package.json").write_text("not-json", encoding="utf-8")
            assert kbn_stack.checkout.read_worktree_version(tmp) is None

    def test_es_instance_state_classifies_port_pid_and_stale(self):
        kbn_stack = _load_kbn_stack_command()
        es_http = kbn_stack.slots.derive(0)["es_http"]
        instance = {"slot": 0, "es_http": es_http, "es_pid": 1234}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            assert kbn_stack.liveness.es_instance_state(instance) == "ready"
        with _patched_ports(kbn_stack, alive_slots={0: (False, False)}):
            with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 1234):
                assert kbn_stack.liveness.es_instance_state(instance) == "starting"
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                assert kbn_stack.liveness.es_instance_state(instance) == "stale"

    def test_claim_creates_instance_on_free_slot_and_truncates_log(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {"/wt/A": {"slot": 1, "backend": "snapshot"}}
        with mock.patch.object(kbn_stack.shared_es.Path, "write_text", autospec=True) as write_text:
            shared = kbn_stack.shared_es.claim_shared_es(
                registry, "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=0
            )

        assert shared["create"] is True
        instance = shared["instance"]
        # Slot 1 (worktree A) is taken and slot 0 (the caller's own slot) is
        # excluded, so dropping the exclusion would wrongly yield slot 0.
        assert instance["slot"] == 2
        assert instance["es_http"] == kbn_stack.slots.derive(2)["es_http"]
        assert instance["data"] == "shared-9.6.0"
        # The log path must be version-keyed: parallel versions must not share
        # a log file (the setup trigger of one would leak into the other).
        assert instance["log"] == "/tmp/es-shared-9.6.0.log"
        assert instance["starting_pid"] == os.getpid()
        assert registry[kbn_stack.config.ES_INSTANCES_KEY]["9.6.0"] is instance
        # The instance log is truncated at claim time so a parallel attacher
        # never reads a stale setup trigger from a previous boot.
        write_text.assert_called_once_with(Path(instance["log"]), "", encoding="utf-8")

    def test_claim_attaches_to_live_instance(self):
        kbn_stack = _load_kbn_stack_command()
        instance = _shared_instance(kbn_stack, 0)
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            shared = kbn_stack.shared_es.claim_shared_es(
                registry, "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=1
            )
        assert shared["create"] is False
        assert shared["instance"] is instance

    def test_allocate_slot_skips_shared_instance_slots(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": {"slot": 1}},
        }
        assert kbn_stack.slots.allocate_slot(registry, "/wt/B", None) == 2

    def test_entry_state_gates_shared_attachee_on_instance_liveness(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": _shared_instance(kbn_stack, 0)}}
        entry = {"slot": 1, "backend": "snapshot", "es_key": "9.6.0", "ready": True}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            assert kbn_stack.liveness.entry_state(registry, entry, False, True, False) == "ready"
            # Dead attachee stays stale/prunable even while the shared ES lives.
            assert kbn_stack.liveness.entry_state(registry, entry, False, False, False) == "stale"
        with _patched_ports(kbn_stack, alive_slots={0: (False, False)}):
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                assert kbn_stack.liveness.entry_state(registry, entry, False, True, False) == "degraded"

    def test_prune_drops_stale_instance_and_keeps_live_unattached_one(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {
                "9.6.0": _shared_instance(kbn_stack, 0),
                "9.4.2": _shared_instance(kbn_stack, 1, version="9.4.2"),
            }
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (False, False)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.lifecycle.run_prune(registry) == 0

        assert set(registry[kbn_stack.config.ES_INSTANCES_KEY]) == {"9.6.0"}
        assert state["killed"] == []
        assert "shared ES 9.4.2" in output.getvalue()

    def test_reclaim_drops_dead_shared_attachee_without_touching_es_ports(self):
        kbn_stack = _load_kbn_stack_command()
        es_http = kbn_stack.slots.derive(0)["es_http"]
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": {"slot": 0, "es_http": es_http}},
            "/wt/B": {"slot": 1, "backend": "snapshot", "es_key": "9.6.0"},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (False, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/C")

        assert changed is True
        assert "/wt/B" not in registry
        assert "9.6.0" in registry[kbn_stack.config.ES_INSTANCES_KEY]
        assert state["killed"] == []

    def test_reclaim_keeps_shared_attachee_with_live_kibana(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": {"slot": 0, "es_http": kbn_stack.slots.derive(0)["es_http"]}},
            "/wt/B": {"slot": 1, "backend": "snapshot", "es_key": "9.6.0"},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (True, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                changed = kbn_stack.lifecycle.reclaim_dead_slots(registry, "/wt/C")

        assert changed is False
        assert "/wt/B" in registry
        assert state["killed"] == []

    def test_stop_shared_attachee_keeps_es_while_others_attached(self):
        kbn_stack = _load_kbn_stack_command()
        es_http = kbn_stack.slots.derive(0)["es_http"]
        kbn_port_b = kbn_stack.slots.derive(1)["kbn_port"]
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": {"slot": 0, "es_http": es_http, "es_pid": 999}},
            "/wt/B": {
                "slot": 1,
                "backend": "snapshot",
                "es_key": "9.6.0",
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            },
            "/wt/C": {
                "slot": 2,
                "backend": "snapshot",
                "es_key": "9.6.0",
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            },
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (True, False), 2: (True, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                rc = kbn_stack.lifecycle.run_stop("/wt/B", registry)

        assert rc == 0
        assert "/wt/B" not in registry
        assert "9.6.0" in registry[kbn_stack.config.ES_INSTANCES_KEY]
        assert state["killed"] == [kbn_port_b]
        assert "left shared ES 9.6.0 running" in output.getvalue()

    def test_stop_last_shared_attachee_stops_the_instance(self):
        kbn_stack = _load_kbn_stack_command()
        es_http = kbn_stack.slots.derive(0)["es_http"]
        kbn_port_b = kbn_stack.slots.derive(1)["kbn_port"]
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": {"slot": 0, "es_http": es_http, "es_pid": 999}},
            "/wt/B": {
                "slot": 1,
                "backend": "snapshot",
                "es_key": "9.6.0",
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            },
        }
        killed_groups: list[int] = []
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (True, False)}) as state:
            with mock.patch.object(kbn_stack.procs, "kill_pid_group", side_effect=killed_groups.append):
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = kbn_stack.lifecycle.run_stop("/wt/B", registry)

        assert rc == 0
        assert registry.get(kbn_stack.config.ES_INSTANCES_KEY) == {}
        assert killed_groups == [999]
        assert set(state["killed"]) == {kbn_port_b, es_http}

    def test_stop_all_clears_shared_instances(self):
        kbn_stack = _load_kbn_stack_command()
        es_http = kbn_stack.slots.derive(0)["es_http"]
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": {"slot": 0, "es_http": es_http, "es_pid": 999}},
            "/wt/B": {
                "slot": 1,
                "backend": "snapshot",
                "es_key": "9.6.0",
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            },
        }
        killed_groups: list[int] = []
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (True, False)}) as state:
            with mock.patch.object(kbn_stack.procs, "kill_pid_group", side_effect=killed_groups.append):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    rc = kbn_stack.lifecycle.run_stop_all(registry)

        assert rc == 0
        assert state["saved"][-1] == {}
        assert killed_groups == [999]
        assert "stopped 2 stack(s)" in output.getvalue()

    def test_serverless_blocks_on_live_shared_instance_in_low_band(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": _shared_instance(kbn_stack, 0)}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            blocked, stopped, _saved = _capture_stop_existing_serverless(
                kbn_stack,
                registry,
                kbn_stack.config.STARTED_BY_AGENT,
            )
        assert blocked is True
        assert stopped == []

    def test_serverless_ignores_shared_attachee_on_conflict_slot(self):
        kbn_stack = _load_kbn_stack_command()
        # The attachee's slot-1 ES ports are unused (its ES lives on slot 5),
        # so it must not block serverless; the instance itself is out of band.
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": {"slot": 5, "es_http": kbn_stack.slots.derive(5)["es_http"]}},
            "/wt/B": {"slot": 1, "backend": "snapshot", "es_key": "9.6.0"},
        }
        with _patched_ports(kbn_stack, alive_slots={5: (False, True)}):
            blocked, stopped, _saved = _capture_stop_existing_serverless(
                kbn_stack,
                registry,
                kbn_stack.config.STARTED_BY_AGENT,
            )
        assert blocked is False
        # Not blocking must not mean stopping: the snapshot attachee is untouched.
        assert stopped == []
        assert "/wt/B" in registry

    def test_es_command_uses_instance_slot_for_node_name(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args([])
        cfg = kbn_stack.slots.derive(3)
        cfg["slot"] = 3
        kbn_stack.shared_es.apply_shared_es(
            cfg, {"slot": 0, "es_url": "http://localhost:9200", "es_http": 9200, "es_transport": 9300}
        )
        settings = _es_dash_e_settings(kbn_stack.launch.es_command(args, cfg, Path("/tmp/es-data"), "yarn"))
        assert "node.name=slot0" in settings
        assert "http.port=9200" in settings
        assert "transport.port=9300" in settings

    def test_status_reports_shared_instance_and_attachee_cells(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {
                "9.6.0": _shared_instance(kbn_stack, 0, started_by=kbn_stack.config.STARTED_BY_AGENT)
            },
            "/wt/B": {
                "slot": 1,
                "backend": "snapshot",
                "branch": "main",
                "es_key": "9.6.0",
                "ready": True,
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            },
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (True, False)}):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                assert kbn_stack.lifecycle.run_status(registry) == 0

        lines = output.getvalue().splitlines()
        assert lines[1].split() == ["ready", "1", "snapshot", "agent", "up", "shared:up", "main", "/wt/B"]
        assert lines[2].split() == ["ready", "0", "shared-es", "agent", "-", "up", "v9.6.0", "(1", "attached)"]

    def test_wrapped_kibana_command_round_trips(self):
        kbn_stack = _load_kbn_stack_command()
        wrapped = kbn_stack.launch.wrapped_kibana_command("yarn start --port=5602", "/wt/a b")
        parts = shlex.split(wrapped)
        assert parts[:2] == ["env", "KBN_STACK_WORKTREE=/wt/a b"]
        assert parts[2] == sys.executable
        assert parts[4:] == ["--run-with-prune", "yarn", "start", "--port=5602"]

    def test_usable_es_instance_rejects_stale_instance(self):
        kbn_stack = _load_kbn_stack_command()
        instance = _shared_instance(kbn_stack, 0, es_pid=999)
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, False)}):
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                assert kbn_stack.shared_es.usable_es_instance(registry, "9.6.0") is None
                # A stale instance must not be attached to: the claim replaces it.
                with mock.patch.object(kbn_stack.shared_es.Path, "write_text", autospec=True):
                    shared = kbn_stack.shared_es.claim_shared_es(
                        registry, "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=1
                    )
        assert shared["create"] is True
        assert shared["instance"] is not instance

    def test_allocate_es_slot_skips_taken_and_excluded_slots(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            "/wt/A": {"slot": 0, "backend": "snapshot"},
            kbn_stack.config.ES_INSTANCES_KEY: {"9.4.2": {"slot": 1}},
        }
        assert kbn_stack.slots.allocate_es_slot(registry, {2}) == 3

    def test_start_path_reclaim_drops_only_stale_instances(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {
                "9.6.0": _shared_instance(kbn_stack, 0),
                "9.4.2": _shared_instance(kbn_stack, 1, version="9.4.2"),
            }
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (False, False)}):
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                with contextlib.redirect_stdout(io.StringIO()):
                    assert kbn_stack.shared_es.reclaim_dead_es_instances(registry) is True
                    assert set(registry[kbn_stack.config.ES_INSTANCES_KEY]) == {"9.6.0"}
                    # A second pass over the now-clean registry reports no change.
                    assert kbn_stack.shared_es.reclaim_dead_es_instances(registry) is False

    def test_build_worktree_entry_records_es_key_for_shared_stacks(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args([])
        cfg = kbn_stack.slots.derive(1)
        cfg["slot"] = 1
        shared_entry = kbn_stack.store.build_worktree_entry(
            args,
            cfg,
            "main",
            "shared-9.6.0",
            Path("/tmp/x.log"),
            kbn_stack.config.STARTED_BY_AGENT,
            "agent-detach",
            "9.6.0",
        )
        assert shared_entry["es_key"] == "9.6.0"
        isolated_entry = kbn_stack.store.build_worktree_entry(
            args, cfg, "main", "mydata", Path("/tmp/x.log"), kbn_stack.config.STARTED_BY_AGENT, "agent-detach", None
        )
        assert "es_key" not in isolated_entry

    def test_reconfirm_attaches_when_another_launcher_won_the_race(self):
        kbn_stack = _load_kbn_stack_command()
        theirs = _shared_instance(kbn_stack, 0, starting_pid=os.getpid() + 1)
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": theirs}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                with contextlib.redirect_stdout(io.StringIO()):
                    _reg, shared = kbn_stack.shared_es.reconfirm_shared_claim(
                        "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=1
                    )
        assert shared["create"] is False
        assert shared["instance"] is theirs

    def test_reconfirm_keeps_create_when_own_claim_survived(self):
        kbn_stack = _load_kbn_stack_command()
        mine = {"slot": 0, "es_http": kbn_stack.slots.derive(0)["es_http"], "starting_pid": os.getpid()}
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": mine}}
        with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
            _reg, shared = kbn_stack.shared_es.reconfirm_shared_claim(
                "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, 1
            )
        assert shared["create"] is True
        assert shared["instance"] is mine

    def test_stop_attachee_never_reclaims_its_unused_es_ports(self):
        kbn_stack = _load_kbn_stack_command()
        # A foreign process squats the attachee slot's ES port (that port is
        # unused by the stack: its ES is the shared instance on slot 0). Stop
        # must not SIGKILL the squatter.
        kbn_port_b = kbn_stack.slots.derive(1)["kbn_port"]
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": {"slot": 0, "es_http": kbn_stack.slots.derive(0)["es_http"]}},
            "/wt/B": {
                "slot": 1,
                "backend": "snapshot",
                "es_key": "9.6.0",
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            },
            "/wt/C": {
                "slot": 2,
                "backend": "snapshot",
                "es_key": "9.6.0",
                "started_by": kbn_stack.config.STARTED_BY_AGENT,
            },
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (True, True), 2: (True, False)}) as state:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = kbn_stack.lifecycle.run_stop("/wt/B", registry)
        assert rc == 0
        assert state["killed"] == [kbn_port_b]

    def test_main_start_wires_shared_es_for_default_snapshot(self):
        kbn_stack = _load_kbn_stack_command()
        instance = _shared_instance(kbn_stack, 0)
        with tempfile.TemporaryDirectory() as tmp:
            worktree = str(Path(tmp).resolve())
            (Path(worktree) / "package.json").write_text('{"version": "9.6.0"}', encoding="utf-8")
            registry = {
                kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance},
                # This worktree's previous isolated stack: Kibana dead, ES alive.
                worktree: {"slot": 1, "backend": "snapshot", "branch": "feat/x"},
            }
            with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (False, True)}) as state:

                def armed(version, inst):
                    # The watchdog reloads the registry from disk at once and exits on an
                    # unknown version, so the claim must already be saved when it starts.
                    assert state["saved"] and state["saved"][-1][worktree]["es_key"] == "9.6.0"
                    return True

                with (
                    mock.patch.object(kbn_stack.checkout, "resolve_worktree", return_value=worktree),
                    mock.patch.object(kbn_stack.checkout, "current_branch", return_value="feat/x"),
                    mock.patch.object(kbn_stack.store, "load_registry", return_value=registry),
                    mock.patch.object(kbn_stack.liveness, "ensure_ports_free") as ports_free,
                    mock.patch.object(kbn_stack.shared_es, "ensure_reaper", side_effect=armed) as reaper,
                    mock.patch.object(kbn_stack.launch.subprocess, "run"),
                    mock.patch.object(kbn_stack.launch, "run_detached", return_value=0) as run_detached,
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    assert kbn_stack.main(["--detach"]) == 0

        run_detached.assert_called_once()
        call = run_detached.call_args
        cfg = call.args[1]
        assert cfg["es_url"] == instance["es_url"]
        assert call.kwargs["shared"]["create"] is False
        assert registry[worktree]["es_key"] == "9.6.0"
        reaper.assert_called_once_with("9.6.0", instance)
        # A spawned reaper records its pid on the instance; that goes to disk too.
        assert len(state["saved"]) >= 2
        # The stranded isolated ES half must be reclaimed, not leaked untracked.
        assert state["killed"] == [kbn_stack.slots.derive(1)["es_http"]]
        # An attach must skip the ES-port free check: the shared ES is
        # legitimately bound to those ports, so checking them would fail
        # every attach in production.
        ports_free.assert_called_once_with(cfg, check_es=False)

    def test_shared_ready_requires_listener_identity(self):
        kbn_stack = _load_kbn_stack_command()
        squatted = _shared_instance(kbn_stack, 0, es_pid=999)
        es_http = kbn_stack.slots.derive(0)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}, squatted_ports=frozenset({es_http})):
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                # A foreign process on the recorded port is not the shared ES.
                assert kbn_stack.liveness.es_instance_state(squatted) == "stale"
                registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": squatted}}
                assert kbn_stack.shared_es.usable_es_instance(registry, "9.6.0") is None
        # A listener with no recorded es_pid is treated as a squatter too:
        # es_pid is registered right after spawn, while the JVM still needs
        # seconds to bind, so a bound port without es_pid is not trusted.
        pidless = _shared_instance(kbn_stack, 0)
        del pidless["es_pid"]
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                assert kbn_stack.liveness.es_instance_state(pidless) == "stale"

    def test_allocate_es_slot_avoids_serverless_band_while_registered(self):
        kbn_stack = _load_kbn_stack_command()
        # Slot 1's ES ports collide with the serverless containers (transport is
        # not preflighted), so the band is excluded while serverless is registered.
        registry = {"/wt/S": {"slot": 0, "backend": "serverless"}}
        assert kbn_stack.slots.allocate_es_slot(registry, set()) == 2
        assert kbn_stack.slots.allocate_es_slot({"/wt/A": {"slot": 0, "backend": "snapshot"}}, set()) == 1

    def test_claim_survives_corrupt_instances_container(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {kbn_stack.config.ES_INSTANCES_KEY: []}
        with mock.patch.object(kbn_stack.shared_es.Path, "write_text", autospec=True):
            shared = kbn_stack.shared_es.claim_shared_es(
                registry, "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=1
            )
        assert shared["create"] is True
        assert registry[kbn_stack.config.ES_INSTANCES_KEY]["9.6.0"] is shared["instance"]

    def test_usable_rejects_instance_missing_endpoint_fields(self):
        kbn_stack = _load_kbn_stack_command()
        no_url = _shared_instance(kbn_stack, 0)
        del no_url["es_url"]
        no_transport = _shared_instance(kbn_stack, 0)
        del no_transport["es_transport"]
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            for broken in (no_url, no_transport):
                registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": broken}}
                assert kbn_stack.shared_es.usable_es_instance(registry, "9.6.0") is None

    def test_reconfirm_replaces_unusable_instance(self):
        kbn_stack = _load_kbn_stack_command()
        broken = _shared_instance(kbn_stack, 0, starting_pid=os.getpid() + 1)
        del broken["es_url"]
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": broken}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                with mock.patch.object(kbn_stack.shared_es.Path, "write_text", autospec=True):
                    with contextlib.redirect_stdout(io.StringIO()):
                        _reg, shared = kbn_stack.shared_es.reconfirm_shared_claim(
                            "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=1
                        )
        assert shared["create"] is True
        assert shared["instance"] is not broken
        # The replacement must respect the caller's excluded slot: with the
        # broken instance on slot 0 and slot 1 excluded, only slot 2 is legal.
        assert shared["instance"]["slot"] == 2

    def test_shared_start_reclaims_stranded_isolated_es(self):
        kbn_stack = _load_kbn_stack_command()
        entry = {"slot": 1, "backend": "snapshot", "es_pid": 777}
        registry = {"/wt/B": entry}
        es_http = kbn_stack.slots.derive(1)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={1: (False, True)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                with contextlib.redirect_stdout(io.StringIO()):
                    kbn_stack.shared_es.clear_previous_stack_for_shared_es(registry, "/wt/B")
        assert state["killed_groups"] == [777]
        assert state["killed"] == [es_http]
        # A shared attachee entry owns no ES half at all.
        shared_entry = {"slot": 1, "backend": "snapshot", "es_key": "9.6.0"}
        with _patched_ports(kbn_stack, alive_slots={1: (False, True)}) as state:
            kbn_stack.shared_es.clear_previous_stack_for_shared_es({"/wt/B": shared_entry}, "/wt/B")
        assert state["killed"] == []

    def test_shared_start_fails_fast_on_owned_previous_stack(self):
        kbn_stack = _load_kbn_stack_command()
        # ES up, Kibana down, but the launcher is alive: a mid-restart stack
        # the user still owns must be named, never killed.
        entry = {"slot": 1, "backend": "snapshot", "es_pid": 777, "started_by_pid": 888}
        registry = {"/wt/B": entry}
        with _patched_ports(kbn_stack, alive_slots={1: (False, True)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 888):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        kbn_stack.shared_es.clear_previous_stack_for_shared_es(registry, "/wt/B")
        assert state["killed_groups"] == []
        assert state["killed"] == []
        # A fully alive old pair is equally owned.
        with _patched_ports(kbn_stack, alive_slots={1: (True, True)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        kbn_stack.shared_es.clear_previous_stack_for_shared_es(registry, "/wt/B")
        assert state["killed_groups"] == []
        assert state["killed"] == []
        # A bootstrapping stack (launcher alive, nothing bound yet) is owned
        # too: overwriting its entry would orphan the whole bootstrap.
        with _patched_ports(kbn_stack, alive_slots={1: (False, False)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 888):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        kbn_stack.shared_es.clear_previous_stack_for_shared_es(registry, "/wt/B")
        assert state["killed_groups"] == []
        assert state["killed"] == []

    def test_shared_start_guards_previous_serverless_stack(self):
        kbn_stack = _load_kbn_stack_command()
        entry = {"slot": 0, "backend": "serverless"}
        registry = {"/wt/B": entry}
        # Live containers: overwriting the entry would leave es01/es02
        # untracked with no --stop path, so the start must fail fast.
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        kbn_stack.shared_es.clear_previous_stack_for_shared_es(registry, "/wt/B")
        assert state["killed"] == []
        # es01 dead but es02 still up on the rest of the band: the entry is
        # still backed by a live container and must not be overwritten.
        with _patched_ports(kbn_stack, alive_slots={0: (False, False), 1: (False, True)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        kbn_stack.shared_es.clear_previous_stack_for_shared_es(registry, "/wt/B")
        assert state["killed"] == []
        # A dead serverless entry may be overwritten quietly.
        with _patched_ports(kbn_stack, alive_slots={0: (False, False)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                kbn_stack.shared_es.clear_previous_stack_for_shared_es(registry, "/wt/B")
        assert state["killed"] == []
        # A registered isolated snapshot on slot 1 whose process tree owns the
        # 9202 listener explains it away: not a serverless survivor.
        shared_registry = {
            "/wt/B": dict(entry),
            "/wt/C": {"slot": 1, "backend": "snapshot", "es_pid": 777},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, False), 1: (False, True)}) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 777):
                kbn_stack.shared_es.clear_previous_stack_for_shared_es(shared_registry, "/wt/B")
        assert state["killed"] == []
        # Identity, not liveness, is what attributes the listener: a merely
        # ALIVE registrant whose tree does not own 9202 (a bootstrapping
        # launcher; the listener is es02) must not mask it.
        bootstrap_registry = {
            "/wt/B": dict(entry),
            "/wt/C": {"slot": 1, "backend": "snapshot", "started_by_pid": 888},
        }
        with _patched_ports(
            kbn_stack,
            alive_slots={0: (False, False), 1: (False, True)},
            squatted_ports=frozenset({kbn_stack.slots.derive(1)["es_http"]}),
        ) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 888):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        kbn_stack.shared_es.clear_previous_stack_for_shared_es(bootstrap_registry, "/wt/B")
        assert state["killed"] == []
        # A dead registrant cannot explain the listener either.
        with _patched_ports(
            kbn_stack,
            alive_slots={0: (False, False), 1: (False, True)},
            squatted_ports=frozenset({kbn_stack.slots.derive(1)["es_http"]}),
        ) as state:
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        kbn_stack.shared_es.clear_previous_stack_for_shared_es(shared_registry, "/wt/B")
        assert state["killed"] == []
        # A shared instance on slot 1 masks the listener only when its own
        # process tree owns it; a live es_pid with a foreign listener (es02
        # squatting while the instance starts) must still block.
        stale_registry = {
            "/wt/B": dict(entry),
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": _shared_instance(kbn_stack, 1)},
        }
        for instance_pid_alive in (False, True):
            with _patched_ports(
                kbn_stack,
                alive_slots={0: (False, False), 1: (False, True)},
                squatted_ports=frozenset({kbn_stack.slots.derive(1)["es_http"]}),
            ) as state:
                with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=instance_pid_alive):
                    with contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit):
                            kbn_stack.shared_es.clear_previous_stack_for_shared_es(stale_registry, "/wt/B")
            assert state["killed"] == []

    def test_claim_stops_live_unusable_instance_before_replacing(self):
        kbn_stack = _load_kbn_stack_command()
        broken = _shared_instance(kbn_stack, 0)
        del broken["es_url"]
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": broken}}
        es_http = kbn_stack.slots.derive(0)["es_http"]
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}) as state:
            with mock.patch.object(kbn_stack.shared_es.Path, "write_text", autospec=True):
                with contextlib.redirect_stdout(io.StringIO()):
                    shared = kbn_stack.shared_es.claim_shared_es(
                        registry, "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=1
                    )
        # The live-but-unusable JVM is stopped, not silently orphaned.
        assert state["killed_groups"] == [broken["es_pid"]]
        assert state["killed"] == [es_http]
        assert shared["create"] is True
        assert shared["instance"] is not broken

    def test_load_registry_normalizes_corrupt_shared_map(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            with mock.patch.object(kbn_stack.config, "REGISTRY_PATH", path):
                path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
                assert kbn_stack.store.load_registry() == {}
                path.write_text(json.dumps({kbn_stack.config.ES_INSTANCES_KEY: ["corrupt"]}), encoding="utf-8")
                assert kbn_stack.store.load_registry() == {}
                good = {"slot": 0}
                path.write_text(
                    json.dumps({kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": [], "9.4.2": good}}),
                    encoding="utf-8",
                )
                assert kbn_stack.store.load_registry() == {kbn_stack.config.ES_INSTANCES_KEY: {"9.4.2": good}}

    def test_usable_rejects_boolean_and_empty_string_fields(self):
        kbn_stack = _load_kbn_stack_command()
        # A bool slot passes bare isinstance(int) checks; the live port keeps
        # the state ready so only the bool rejection can flag it.
        bool_slot = _shared_instance(kbn_stack, 0)
        bool_slot["slot"] = True
        empty_log = _shared_instance(kbn_stack, 0, log="")
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            for broken in (bool_slot, empty_log):
                registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": broken}}
                assert kbn_stack.shared_es.usable_es_instance(registry, "9.6.0") is None

    def test_wait_for_shared_es_ignores_squatter_listener(self):
        kbn_stack = _load_kbn_stack_command()
        instance = _shared_instance(kbn_stack, 0)
        es_http = instance["es_http"]
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(kbn_stack.config.TRIGGER_STRING + "\n", encoding="utf-8")
            shared = {"key": "9.6.0", "create": False, "instance": instance}
            # Identity-verified listener: fast path, no waiting banner.
            with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    kbn_stack.shared_es.wait_for_shared_es(shared, logfile)
            assert "waiting for shared ES" not in output.getvalue()
            # A stale trigger plus a squatter on the port must fail the attach:
            # the log survives an ES death, so the trigger alone proves nothing.
            registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
            with _patched_ports(kbn_stack, alive_slots={0: (False, True)}, squatted_ports=frozenset({es_http})):
                with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                    with mock.patch.object(kbn_stack.config, "SHARED_ES_CONFIRM_TIMEOUT", 0):
                        with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                            with contextlib.redirect_stdout(io.StringIO()):
                                with contextlib.redirect_stderr(io.StringIO()) as err:
                                    with self.assertRaises(SystemExit):
                                        kbn_stack.shared_es.wait_for_shared_es(shared, logfile)
            assert "stale trigger, foreign listener" in err.getvalue()

    def test_wait_for_shared_es_confirms_identity_after_trigger(self):
        kbn_stack = _load_kbn_stack_command()
        # The claim snapshot has no es_pid yet (creator still bootstrapping):
        # the fast path cannot verify identity, so the attach takes the trigger
        # path and must confirm readiness from the reloaded registry.
        snapshot = _shared_instance(kbn_stack, 0)
        del snapshot["es_pid"]
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": _shared_instance(kbn_stack, 0)}}
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(kbn_stack.config.TRIGGER_STRING + "\n", encoding="utf-8")
            shared = {"key": "9.6.0", "create": False, "instance": snapshot}
            with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
                with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                    with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                        with contextlib.redirect_stdout(io.StringIO()) as output:
                            kbn_stack.shared_es.wait_for_shared_es(shared, logfile)
        assert "waiting for shared ES" in output.getvalue()

    def test_wait_for_shared_es_rejects_replacement_instance(self):
        kbn_stack = _load_kbn_stack_command()
        # The claimed slot-0 instance died mid-setup and another launcher
        # created a ready replacement on slot 2. The caller's cfg points at
        # slot 0, so the replacement being ready must not authorize the attach.
        snapshot = _shared_instance(kbn_stack, 0)
        del snapshot["es_pid"]
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": _shared_instance(kbn_stack, 2)}}
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(kbn_stack.config.TRIGGER_STRING + "\n", encoding="utf-8")
            shared = {"key": "9.6.0", "create": False, "instance": snapshot}
            with _patched_ports(kbn_stack, alive_slots={2: (False, True)}):
                with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                    with mock.patch.object(kbn_stack.config, "SHARED_ES_CONFIRM_TIMEOUT", 0.05):
                        with mock.patch.object(kbn_stack.shared_es.time, "sleep", lambda seconds: None):
                            with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                                with contextlib.redirect_stdout(io.StringIO()):
                                    with contextlib.redirect_stderr(io.StringIO()) as err:
                                        with self.assertRaises(SystemExit):
                                            kbn_stack.shared_es.wait_for_shared_es(shared, logfile)
        assert "replaced mid-setup" in err.getvalue()

    def test_claim_fails_when_unusable_instance_still_referenced(self):
        kbn_stack = _load_kbn_stack_command()
        broken = _shared_instance(kbn_stack, 0)
        del broken["es_url"]
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": broken},
            "/wt/A": {"slot": 1, "backend": "snapshot", "es_key": "9.6.0"},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}) as state:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit):
                    kbn_stack.shared_es.claim_shared_es(
                        registry, "9.6.0", "/wt/B", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=2
                    )
        # The ES serving worktree A must never be killed out from under it.
        assert state["killed_groups"] == []
        assert state["killed"] == []
        assert "/wt/A" in err.getvalue()

    def test_when_serverless_boot_is_interrupted_should_keep_es_pid_for_cleanup(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["--detach", "--es", "serverless"])
        cfg = {**kbn_stack.slots.derive(0), "slot": 0, "es_url": "https://localhost:9200"}
        on_disk = {"/wt/A": {"slot": 0, "backend": "serverless", "ready": False}}
        with self._detached_boot(kbn_stack, on_disk) as saved:
            with mock.patch.object(kbn_stack.es_log, "wait_for_trigger", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    kbn_stack.launch.run_detached(
                        args, cfg, "/wt/A", Path("/tmp/es-data"), Path("/tmp/es.log"), "yarn start"
                    )
        self.assertEqual(saved[-1]["/wt/A"]["es_pid"], 111)
        self.assertFalse(saved[-1]["/wt/A"]["ready"])

    def test_when_serverless_starts_should_skip_snapshot_trial_license_setup(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["--detach", "--es", "serverless"])
        cfg = {**kbn_stack.slots.derive(0), "slot": 0, "es_url": "https://localhost:9200"}
        on_disk = {"/wt/A": {"slot": 0, "backend": "serverless", "ready": False}}
        with self._detached_boot(kbn_stack, on_disk):
            with mock.patch.object(kbn_stack.trial_license, "ensure_trial_license") as trial:
                kbn_stack.launch.run_detached(
                    args, cfg, "/wt/A", Path("/tmp/es-data"), Path("/tmp/es.log"), "yarn start"
                )
        trial.assert_not_called()

    @contextlib.contextmanager
    def _detached_boot(self, kbn_stack, on_disk: dict, es_pid: int = 111, kbn_pid: int = 222):
        """Fake a successful detached boot over an on-disk registry that keeps changing.

        ``load_registry`` returns a fresh copy of ``on_disk`` each call (another
        launcher's writes are already there); ``saved`` records every write.
        """
        saved: list[dict] = []
        with (
            mock.patch.object(kbn_stack.launch, "spawn_background", side_effect=[es_pid, kbn_pid]),
            mock.patch.object(kbn_stack.es_log, "wait_for_trigger", return_value=kbn_stack.config.WAIT_TRIGGER),
            mock.patch.object(kbn_stack.trial_license, "ensure_trial_license"),
            mock.patch.object(kbn_stack.launch, "kibana_ready", return_value=True),
            mock.patch.object(kbn_stack.procs, "listener_identity_ok", return_value=(True, [kbn_pid])),
            mock.patch.object(kbn_stack.store, "load_registry", side_effect=lambda: json.loads(json.dumps(on_disk))),
            mock.patch.object(kbn_stack.store, "save_registry", side_effect=saved.append),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            yield saved

    def test_run_detached_merges_into_reloaded_registry(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["--detach"])
        cfg = kbn_stack.slots.derive(1)
        cfg["slot"] = 1
        # Worktree B attached to the shared ES while this launcher was booting:
        # its entry exists only on disk, never in this launcher's snapshot.
        on_disk = {
            "/wt/A": {"slot": 1, "backend": "snapshot", "ready": False},
            "/wt/B": {"slot": 2, "backend": "snapshot", "es_key": "9.6.0"},
        }
        with self._detached_boot(kbn_stack, on_disk) as saved:
            rc = kbn_stack.launch.run_detached(
                args, cfg, "/wt/A", Path("/tmp/es-data"), Path("/tmp/es.log"), "yarn start"
            )

        assert rc == 0
        final = saved[-1]
        # B survives: losing it would drop it from the shared-ES refcount.
        assert final["/wt/B"] == on_disk["/wt/B"]
        assert final["/wt/A"]["es_pid"] == 111
        assert final["/wt/A"]["kbn_pid"] == 222
        assert final["/wt/A"]["ready"] is True

    def test_run_detached_shared_create_records_pid_on_instance_only(self):
        kbn_stack = _load_kbn_stack_command()
        args = kbn_stack.cli.parse_args(["--detach"])
        cfg = kbn_stack.slots.derive(1)
        cfg["slot"] = 1
        instance = _shared_instance(kbn_stack, 0)
        del instance["es_pid"]
        kbn_stack.shared_es.apply_shared_es(cfg, instance)
        on_disk = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": dict(instance)},
            "/wt/A": {"slot": 1, "backend": "snapshot", "es_key": "9.6.0", "ready": False},
        }
        shared = {"key": "9.6.0", "create": True, "instance": instance}
        with self._detached_boot(kbn_stack, on_disk) as saved:
            rc = kbn_stack.launch.run_detached(
                args, cfg, "/wt/A", Path("/tmp/es-data"), Path("/tmp/es.log"), "yarn start", shared=shared
            )

        assert rc == 0
        # The ES pid lands on the shared instance right after spawn ...
        assert saved[0][kbn_stack.config.ES_INSTANCES_KEY]["9.6.0"]["es_pid"] == 111
        # ... and never on the attachee entry, whose --stop must not touch the ES.
        assert "es_pid" not in saved[-1]["/wt/A"]
        assert saved[-1]["/wt/A"]["kbn_pid"] == 222


class TestKbnStackLicenseLifecycle(unittest.TestCase):
    """WHEN a persistent snapshot data dir outlives its 30-day trial or ES dies during setup."""

    def test_wait_for_trigger_reports_expired_trial_from_es_log(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text(
                "   │ info [o.e.l.ClusterStateLicenseService] [slot0] license [76d9] mode [trial] - valid\n"
                "   │ warn [o.e.l.ClusterStateLicenseService] [slot0] LICENSE [EXPIRED] ON [SATURDAY, AUGUST 29, 2026].\n",
                encoding="utf-8",
            )
            assert kbn_stack.es_log.wait_for_trigger(logfile, timeout=1) == kbn_stack.config.WAIT_EXPIRED

    def test_wait_for_trigger_reports_exit_as_soon_as_the_launcher_is_gone(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text("   │ERROR Error: ES cluster failed to come online with the 120 second timeout\n")
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False) as alive:
                with mock.patch.object(kbn_stack.es_log.time, "sleep") as sleep:
                    verdict = kbn_stack.es_log.wait_for_trigger(logfile, timeout=600, es_pid=4242)
        assert verdict == kbn_stack.config.WAIT_EXITED
        alive.assert_called_once_with(4242)
        sleep.assert_not_called()

    def test_wait_for_trigger_prefers_a_trigger_flushed_right_before_exit(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text("", encoding="utf-8")

            def flush_trigger(pid):
                logfile.write_text(f"{kbn_stack.config.TRIGGER_STRING}\n", encoding="utf-8")
                return False

            with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=flush_trigger):
                verdict = kbn_stack.es_log.wait_for_trigger(logfile, timeout=600, es_pid=4242)
        assert verdict == kbn_stack.config.WAIT_TRIGGER

    def test_wait_for_trigger_times_out_while_the_launcher_lives(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text("", encoding="utf-8")
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=True):
                with mock.patch.object(kbn_stack.es_log.time, "monotonic", side_effect=[0.0, 0.5, 1.5]):
                    with mock.patch.object(kbn_stack.es_log.time, "sleep"):
                        verdict = kbn_stack.es_log.wait_for_trigger(logfile, timeout=1, es_pid=4242)
        assert verdict == kbn_stack.config.WAIT_TIMEOUT

    def test_log_readers_rewind_after_a_respawn_truncates_the_log(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text("first boot line one\nfirst boot line two\n", encoding="utf-8")
            with kbn_stack.es_log.LogFollower(logfile) as log:
                assert log.readline() == "first boot line one\n"
                assert log.readline() == "first boot line two\n"
                assert log.readline() == ""
                logfile.write_text("short\n", encoding="utf-8")
                assert log.readline() == "short\n"
                assert log.readline() == ""
                # A rewrite that already outgrew the old offset is caught by its changed first line.
                logfile.write_text("second boot line one\nsecond boot line two\n", encoding="utf-8")
                assert log.readline() == "second boot line one\n"
                assert log.readline() == "second boot line two\n"
                # Plain appends are not a rewrite.
                with logfile.open("a", encoding="utf-8") as writer:
                    writer.write("appended\n")
                assert log.readline() == "appended\n"

    def test_spawn_background_opens_the_log_with_a_unique_boot_marker(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            pid = kbn_stack.launch.spawn_background(["true"], logfile, tmp)
            first = logfile.read_text(encoding="utf-8").splitlines()[0]
        assert pid > 0
        assert first.startswith(",kbn-stack: Elasticsearch log opened ")
        assert kbn_stack.es_log.boot_marker() != kbn_stack.es_log.boot_marker()

    def test_record_license_writes_the_data_dir_sidecar(self):
        kbn_stack = _load_kbn_stack_command()
        payload = json.dumps(
            {"license": {"type": "trial", "status": "active", "expiry_date_in_millis": 1790000000000, "uid": "x"}}
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "main"
            data_path.mkdir()
            with mock.patch.object(
                kbn_stack.trial_license.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout=payload),
            ) as run:
                kbn_stack.trial_license.record_license("http://localhost:9200", data_path)
            record = json.loads((data_path / kbn_stack.config.LICENSE_SIDECAR).read_text(encoding="utf-8"))
        assert run.call_args.args[0][-1] == "http://localhost:9200/_license"
        assert record["type"] == "trial"
        assert record["expiry_date_in_millis"] == 1790000000000
        assert kbn_stack.trial_license.recorded_license_expiry(data_path) is None  # dir gone with tmp

    def test_ensure_trial_license_records_after_start_trial(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "main"
            data_path.mkdir()
            with mock.patch.object(
                kbn_stack.trial_license.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
            ):
                with mock.patch.object(kbn_stack.trial_license, "record_license") as record:
                    kbn_stack.trial_license.ensure_trial_license("http://localhost:9200", data_path)
        record.assert_called_once_with("http://localhost:9200", data_path)

    def test_preflight_rotates_only_a_dir_whose_recorded_trial_expired(self):
        kbn_stack = _load_kbn_stack_command()
        now = 1_800_000_000_000
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, expiry in (("expired", now - 1), ("valid", now + 1), ("perpetual", None)):
                (root / name).mkdir()
                (root / name / kbn_stack.config.LICENSE_SIDECAR).write_text(
                    json.dumps({"type": "trial", "expiry_date_in_millis": expiry}), encoding="utf-8"
                )
            (root / "legacy").mkdir()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                rotated = kbn_stack.trial_license.settle_expired_data_dir(root / "expired", now_millis=now)
                assert kbn_stack.trial_license.settle_expired_data_dir(root / "valid", now_millis=now) is None
                assert kbn_stack.trial_license.settle_expired_data_dir(root / "perpetual", now_millis=now) is None
                assert kbn_stack.trial_license.settle_expired_data_dir(root / "legacy", now_millis=now) is None
                assert kbn_stack.trial_license.settle_expired_data_dir(root / "missing", now_millis=now) is None
            assert rotated is not None
            assert rotated.parent == root
            assert rotated.name.startswith("expired.expired-")
            assert not (root / "expired").exists()
            assert (rotated / kbn_stack.config.LICENSE_SIDECAR).is_file()
            assert (root / "valid").is_dir() and (root / "legacy").is_dir()
        assert "trial license expired on" in output.getvalue()
        assert str(rotated) in output.getvalue()

    def test_detached_start_rotates_expired_dir_and_respawns_once(self):
        kbn_stack = _load_kbn_stack_command()
        pids = iter([111, 222])
        recorded: list[int] = []
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "main"
            data_path.mkdir()
            logfile = Path(tmp) / "es.log"
            logfile.write_text("", encoding="utf-8")
            with mock.patch.object(
                kbn_stack.es_log,
                "wait_for_trigger",
                side_effect=[kbn_stack.config.WAIT_EXPIRED, kbn_stack.config.WAIT_TRIGGER],
            ) as wait:
                with mock.patch.object(kbn_stack.procs, "stop_es_process") as stop:
                    with contextlib.redirect_stdout(io.StringIO()) as output:
                        es_pid = kbn_stack.launch.start_es_and_wait(
                            lambda: next(pids), recorded.append, logfile, data_path, kbn_stack.config.TRIGGER_STRING
                        )
            rotated = [p for p in Path(tmp).iterdir() if p.name.startswith("main.expired-")]
            assert not data_path.exists()
        assert es_pid == 222
        assert recorded == [111, 222]
        stop.assert_called_once_with(111)
        assert len(rotated) == 1
        assert [call.kwargs["es_pid"] for call in wait.call_args_list] == [111, 222]
        assert "expired trial license" in output.getvalue()

    def test_detached_start_fails_fast_with_log_excerpt_when_es_exits(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "main"
            logfile = Path(tmp) / "es.log"
            logfile.write_text(
                "   │ info [o.e.n.Node] [slot0] starting ...\n"
                "   │ERROR Error: ES cluster failed to come online with the 120 second timeout\n"
                "   │ info [o.e.n.Node] [slot0] closed\n",
                encoding="utf-8",
            )
            with mock.patch.object(kbn_stack.es_log, "wait_for_trigger", return_value=kbn_stack.config.WAIT_EXITED):
                with contextlib.redirect_stdout(io.StringIO()):
                    with contextlib.redirect_stderr(io.StringIO()) as err:
                        with self.assertRaises(SystemExit):
                            kbn_stack.launch.start_es_and_wait(
                                lambda: 333, lambda pid: None, logfile, data_path, kbn_stack.config.TRIGGER_STRING
                            )
        message = err.getvalue()
        assert "exited before finishing setup" in message
        assert "ES cluster failed to come online" in message
        assert "[slot0] closed" in message

    def test_detached_start_does_not_rotate_on_timeout_or_second_expiry(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "main"
            data_path.mkdir()
            logfile = Path(tmp) / "es.log"
            logfile.write_text("", encoding="utf-8")
            with mock.patch.object(kbn_stack.es_log, "wait_for_trigger", return_value=kbn_stack.config.WAIT_TIMEOUT):
                with contextlib.redirect_stdout(io.StringIO()):
                    with contextlib.redirect_stderr(io.StringIO()) as err:
                        with self.assertRaises(SystemExit):
                            kbn_stack.launch.start_es_and_wait(
                                lambda: 444, lambda pid: None, logfile, data_path, kbn_stack.config.TRIGGER_STRING
                            )
            assert data_path.is_dir()
        assert "did not finish setup within 600s" in err.getvalue()

    def test_foreground_es_rotates_on_expired_marker_and_restarts_once(self):
        kbn_stack = _load_kbn_stack_command()
        first = mock.Mock(pid=501)
        first.stdout = iter(["boot\n", "   │ warn LICENSE [EXPIRED] ON [SATURDAY].\n", "shutting down\n"])
        first.wait.return_value = 143
        second = mock.Mock(pid=502)
        second.stdout = iter(["fresh boot\n", f"{kbn_stack.config.TRIGGER_STRING}\n"])
        second.wait.return_value = 0
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "main"
            data_path.mkdir()
            logfile = Path(tmp) / "es.log"
            with mock.patch.object(kbn_stack.launch.subprocess, "Popen", side_effect=[first, second]) as popen:
                with mock.patch.object(kbn_stack.procs, "kill_pid_group") as kill:
                    with mock.patch.object(kbn_stack.store, "load_registry", return_value={}):
                        with mock.patch.object(kbn_stack.lifecycle, "run_prune"):
                            with contextlib.redirect_stdout(io.StringIO()) as output:
                                rc = kbn_stack.launch.run_foreground_es(["pnpm", "es"], logfile, data_path=data_path)
            log_text = logfile.read_text(encoding="utf-8")
            assert not data_path.exists()
            assert [p for p in Path(tmp).iterdir() if p.name.startswith("main.expired-")]
        assert rc == 0
        assert popen.call_count == 2
        kill.assert_called_once_with(501)
        marker, *rest = log_text.splitlines(keepends=True)
        assert marker.startswith(",kbn-stack: Elasticsearch log opened ")
        assert rest == ["fresh boot\n", f"{kbn_stack.config.TRIGGER_STRING}\n"]
        assert "expired trial license" in output.getvalue()

    def test_shared_follower_respawns_once_on_expired_marker(self):
        kbn_stack = _load_kbn_stack_command()
        with tempfile.TemporaryDirectory() as tmp:
            logfile = Path(tmp) / "es.log"
            logfile.write_text("   │ERROR blocking [cluster:monitor/health] operation due to expired license.\n")
            respawn = mock.Mock(return_value=777)
            with mock.patch.object(kbn_stack.procs, "stop_es_process") as stop:
                with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=[False]):
                    with mock.patch.object(kbn_stack.store, "load_registry", return_value={}):
                        with mock.patch.object(kbn_stack.lifecycle, "run_prune"):
                            with contextlib.redirect_stdout(io.StringIO()) as output:
                                rc = kbn_stack.launch.follow_es_log(logfile, 666, respawn=respawn)
        assert rc == 1
        stop.assert_called_once_with(666)
        respawn.assert_called_once_with()
        assert "shared ES process (pid 777) exited" in output.getvalue()


class TestKbnStackSharedEsHousekeeping(unittest.TestCase):
    """WHEN a shared ES loses its last consumer or a branch would mutate the shared cluster."""

    def test_settle_stamps_then_reaps_an_unreferenced_shared_es(self):
        kbn_stack = _load_kbn_stack_command()
        instance = _shared_instance(kbn_stack, 0)
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
        now = 1_000_000.0
        window = kbn_stack.config.SHARED_ES_IDLE_TIMEOUT
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            with mock.patch.object(kbn_stack.shared_es, "stop_es_instance") as stop:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.shared_es.settle_idle_es_instances(registry, now=now) is True
                    assert instance["unattached_since"] == int(now)
                    # Inside the window the instance stays warm and the registry is untouched.
                    assert kbn_stack.shared_es.settle_idle_es_instances(registry, now=now + window / 2) is False
                    # A start about to attach never reaps its own target; attaching clears the stamp.
                    late = now + window + 1
                    assert kbn_stack.shared_es.settle_idle_es_instances(registry, keep="9.6.0", now=late) is True
                    assert "unattached_since" not in instance
                    assert kbn_stack.shared_es.settle_idle_es_instances(registry, now=late) is True
                    stop.assert_not_called()
                    assert kbn_stack.shared_es.settle_idle_es_instances(registry, now=late + window) is True
        stop.assert_called_once_with("9.6.0", instance)
        assert "9.6.0" not in registry[kbn_stack.config.ES_INSTANCES_KEY]
        assert "no Kibana client for 60s" in output.getvalue()

    def test_settle_clears_stamp_for_a_live_client_and_ignores_stale_instances(self):
        kbn_stack = _load_kbn_stack_command()
        attached = _shared_instance(kbn_stack, 0, unattached_since=5)
        stale = _shared_instance(kbn_stack, 2, version="8.19.0", unattached_since=5)
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": attached, "8.19.0": stale},
            # Kibana listening on slot 1: a live client.
            "/wt/A": {"slot": 1, "backend": "snapshot", "es_key": "9.6.0", "ready": True},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (True, False)}):
            with mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False):
                with mock.patch.object(kbn_stack.shared_es, "stop_es_instance") as stop:
                    old = 5 + kbn_stack.config.SHARED_ES_IDLE_TIMEOUT * 10
                    assert kbn_stack.shared_es.settle_idle_es_instances(registry, now=old) is True
        assert "unattached_since" not in attached
        # Dead instances belong to the stale-reclaim path, not to idle reaping.
        assert stale["unattached_since"] == 5 and "8.19.0" in registry[kbn_stack.config.ES_INSTANCES_KEY]
        stop.assert_not_called()

    def test_claim_attach_clears_idle_stamp(self):
        kbn_stack = _load_kbn_stack_command()
        instance = _shared_instance(kbn_stack, 0, unattached_since=5)
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            shared = kbn_stack.shared_es.claim_shared_es(
                registry, "9.6.0", "/wt/A", kbn_stack.config.STARTED_BY_AGENT, exclude_slot=1
            )
        assert shared["create"] is False
        assert "unattached_since" not in instance

    def test_prune_reaps_a_shared_es_idle_past_the_window(self):
        kbn_stack = _load_kbn_stack_command()
        since = int(time.time() - kbn_stack.config.SHARED_ES_IDLE_TIMEOUT - 60)
        instance = _shared_instance(kbn_stack, 0, unattached_since=since)
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}) as state:
            with mock.patch.object(kbn_stack.shared_es, "stop_es_instance") as stop:
                with contextlib.redirect_stdout(io.StringIO()):
                    assert kbn_stack.lifecycle.run_prune(registry, quiet=True) == 0
        stop.assert_called_once_with("9.6.0", instance)
        assert registry[kbn_stack.config.ES_INSTANCES_KEY] == {}
        assert len(state["saved"]) == 1

    def test_status_shows_how_long_a_shared_es_has_had_no_client(self):
        kbn_stack = _load_kbn_stack_command()
        now = 1_800_000_000.0
        instance = _shared_instance(kbn_stack, 0, unattached_since=int(now - 45))
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance},
            # Attached but its Kibana is gone: still listed, no longer a client.
            "/wt/A": {"slot": 1, "backend": "snapshot", "es_key": "9.6.0", "ready": True},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}) as state:
            with (
                mock.patch.object(kbn_stack.procs, "pid_alive", return_value=False),
                mock.patch.object(kbn_stack.lifecycle.time, "time", return_value=now),
            ):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    assert kbn_stack.lifecycle.run_status(registry) == 0
        assert "(1 attached, no client 45s)" in output.getvalue()
        assert state["saved"] == []

    def test_shared_es_clients_count_listening_or_still_starting_kibanas(self):
        kbn_stack = _load_kbn_stack_command()
        registry = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": _shared_instance(kbn_stack, 0)},
            "/wt/listening": {"slot": 1, "es_key": "9.6.0", "ready": True},
            "/wt/bootstrapping": {"slot": 2, "es_key": "9.6.0", "ready": False, "started_by_pid": 7001},
            "/wt/kibana-gone": {"slot": 3, "es_key": "9.6.0", "ready": True, "started_by_pid": 7002},
            "/wt/isolated": {"slot": 4, "ready": True},
            # Dev-mode server restart: port unbound, but the recorded Kibana process lives.
            "/wt/restarting": {"slot": 5, "es_key": "9.6.0", "ready": True, "kbn_pid": 7003},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True), 1: (True, False)}):
            with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid in (7001, 7002, 7003)):
                clients = kbn_stack.liveness.shared_es_clients(registry, "9.6.0")
        # A launcher still following the ES log after its Kibana died is not a client.
        assert clients == ["/wt/listening", "/wt/bootstrapping", "/wt/restarting"]

    def test_ensure_reaper_spawns_a_detached_watchdog_once(self):
        kbn_stack = _load_kbn_stack_command()
        instance = _shared_instance(kbn_stack, 0)
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "reaper.log"
            with mock.patch.object(kbn_stack.config, "shared_es_reaper_log", return_value=log):
                with mock.patch.object(
                    kbn_stack.shared_es.subprocess, "Popen", return_value=mock.Mock(pid=9001)
                ) as popen:
                    with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 9001):
                        assert kbn_stack.shared_es.ensure_reaper("9.6.0", instance) is True
                        assert instance["reaper_pid"] == 9001
                        assert kbn_stack.shared_es.ensure_reaper("9.6.0", instance) is False
        popen.assert_called_once()
        argv = popen.call_args.args[0]
        assert argv[1:] == [str(kbn_stack.config.ENTRYPOINT), "--reap-shared-es", "9.6.0"]
        assert popen.call_args.kwargs["start_new_session"] is True

    def test_reaper_stops_the_es_after_the_grace_and_exits(self):
        kbn_stack = _load_kbn_stack_command()
        since = int(time.time() - kbn_stack.config.SHARED_ES_IDLE_TIMEOUT - 5)
        instance = _shared_instance(kbn_stack, 0, unattached_since=since, reaper_pid=os.getpid())
        registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}) as state:
            with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                with mock.patch.object(kbn_stack.shared_es, "stop_es_instance") as stop:
                    with contextlib.redirect_stdout(io.StringIO()):
                        rc = kbn_stack.shared_es.run_reap_shared_es("9.6.0", sleep=lambda s: None)
        assert rc == 0
        stop.assert_called_once_with("9.6.0", instance)
        assert state["saved"][-1][kbn_stack.config.ES_INSTANCES_KEY] == {}

    def test_reaper_saves_onto_a_fresh_snapshot_so_a_parallel_launcher_entry_survives(self):
        kbn_stack = _load_kbn_stack_command()
        since = int(time.time() - kbn_stack.config.SHARED_ES_IDLE_TIMEOUT - 5)
        instance = _shared_instance(kbn_stack, 0, unattached_since=since, reaper_pid=os.getpid())
        stale = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
        # While the reaper probed liveness, a launcher saved a new isolated worktree.
        fresh = {
            kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": dict(instance), "9.7.0": _shared_instance(kbn_stack, 2)},
            "/wt/new": {"slot": 3, "backend": "snapshot", "ready": False},
        }
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}) as state:
            with mock.patch.object(kbn_stack.store, "load_registry", side_effect=[stale, fresh]):
                with mock.patch.object(kbn_stack.shared_es, "stop_es_instance"):
                    with contextlib.redirect_stdout(io.StringIO()):
                        assert kbn_stack.shared_es.run_reap_shared_es("9.6.0", sleep=lambda s: None) == 0
        saved = state["saved"][-1]
        assert "/wt/new" in saved
        assert list(saved[kbn_stack.config.ES_INSTANCES_KEY]) == ["9.7.0"]

    def test_reaper_exits_when_the_instance_is_gone_or_another_reaper_owns_it(self):
        kbn_stack = _load_kbn_stack_command()
        owned = _shared_instance(kbn_stack, 0, reaper_pid=4321)
        with mock.patch.object(kbn_stack.store, "load_registry", return_value={}):
            assert kbn_stack.shared_es.run_reap_shared_es("9.6.0", sleep=lambda s: None) == 0
        with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
            with mock.patch.object(kbn_stack.procs, "pid_alive", side_effect=lambda pid: pid == 4321):
                registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": owned}}
                with mock.patch.object(kbn_stack.store, "load_registry", return_value=registry):
                    assert kbn_stack.shared_es.run_reap_shared_es("9.6.0", sleep=lambda s: None) == 0
        assert "unattached_since" not in owned

    def test_stop_es_instance_kills_the_reaper_unless_it_is_the_caller(self):
        kbn_stack = _load_kbn_stack_command()
        killed: list[int] = []
        with mock.patch.object(kbn_stack.procs, "kill_pid_group", side_effect=killed.append):
            with mock.patch.object(kbn_stack.procs, "kill_port_listeners"):
                with contextlib.redirect_stdout(io.StringIO()):
                    kbn_stack.shared_es.stop_es_instance("9.6.0", _shared_instance(kbn_stack, 0, reaper_pid=5555))
                    kbn_stack.shared_es.stop_es_instance(
                        "9.6.0", _shared_instance(kbn_stack, 0, reaper_pid=os.getpid())
                    )
        assert killed == [4242, 5555, 4242]

    def test_main_dispatches_the_hidden_reaper_subcommand(self):
        kbn_stack = _load_kbn_stack_command()
        with mock.patch.object(kbn_stack.shared_es, "run_reap_shared_es", return_value=0) as reap:
            assert kbn_stack.main(["--reap-shared-es", "9.6.0"]) == 0
        reap.assert_called_once_with("9.6.0")

    def test_isolation_signal_paths_match_server_side_definitions_only(self):
        kbn_stack = _load_kbn_stack_command()
        paths = [
            "x-pack/platform/plugins/shared/cases/server/saved_object_types/cases.ts",
            "src/platform/plugins/shared/dashboard/server/dashboard_saved_object/dashboard_saved_object.ts",
            "x-pack/platform/plugins/shared/alerting/server/saved_objects/model_versions/rule_model_versions.ts",
            "x-pack/platform/plugins/shared/fleet/server/services/epm/elasticsearch/index_template/install.ts",
            "src/core/packages/saved-objects/base-server-internal/src/model_version/model_version_map.ts",
            "src/platform/plugins/shared/data/server/saved_objects/query.test.ts",
            "src/platform/plugins/shared/data/public/saved_objects/query.ts",
            "src/platform/plugins/shared/data/server/routes/search.ts",
            "src/platform/plugins/shared/data/server/saved_objects/__mocks__/index.ts",
        ]
        assert kbn_stack.checkout.isolation_signal_paths(paths) == paths[:5]

    def test_isolation_signals_diff_the_branch_against_its_merge_base(self):
        kbn_stack = _load_kbn_stack_command()

        def git(args):
            if args[2:] == ["merge-base", "HEAD", "origin/main"]:
                return "abc123"
            if args[2:] == ["diff", "--name-only", "abc123"]:
                return "src/platform/plugins/shared/data/server/saved_objects/query.ts\nREADME.md\n"
            if args[2:] == ["ls-files", "--others", "--exclude-standard"]:
                # A new saved-object type file before `git add` is invisible to `git diff`.
                return "x-pack/platform/plugins/shared/cases/server/saved_object_types/new_type.ts\nnotes.md\n"
            raise AssertionError(args)

        with mock.patch.object(kbn_stack.checkout, "git_output", side_effect=git):
            assert kbn_stack.checkout.isolation_signals("/wt") == [
                "src/platform/plugins/shared/data/server/saved_objects/query.ts",
                "x-pack/platform/plugins/shared/cases/server/saved_object_types/new_type.ts",
            ]
        with mock.patch.object(kbn_stack.checkout, "git_output", return_value=""):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                assert kbn_stack.checkout.isolation_signals("/not-a-repo") == []
        assert "skipping the saved-object isolation check" in output.getvalue()

    def test_parse_args_rejects_share_es_with_isolated_es(self):
        kbn_stack = _load_kbn_stack_command()
        with contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                kbn_stack.cli.parse_args(["--share-es", "--isolated-es"])
        assert "mutually exclusive" in err.getvalue()
        assert kbn_stack.cli.parse_args(["--share-es"]).share_es is True

    def _start_with_signals(self, kbn_stack, argv: list[str], signals: list[str]):
        instance = _shared_instance(kbn_stack, 0)
        with tempfile.TemporaryDirectory() as tmp:
            worktree = str(Path(tmp).resolve())
            (Path(worktree) / "package.json").write_text('{"version": "9.6.0"}', encoding="utf-8")
            registry = {kbn_stack.config.ES_INSTANCES_KEY: {"9.6.0": instance}}
            with _patched_ports(kbn_stack, alive_slots={0: (False, True)}):
                with (
                    mock.patch.object(kbn_stack.checkout, "resolve_worktree", return_value=worktree),
                    mock.patch.object(kbn_stack.checkout, "current_branch", return_value="feat/so"),
                    mock.patch.object(kbn_stack.checkout, "isolation_signals", return_value=signals) as probe,
                    mock.patch.object(kbn_stack.store, "load_registry", return_value=registry),
                    mock.patch.object(kbn_stack.liveness, "ensure_ports_free"),
                    mock.patch.object(kbn_stack.shared_es, "ensure_reaper", return_value=False),
                    mock.patch.object(kbn_stack.shared_es.Path, "write_text", autospec=True),
                    mock.patch.object(kbn_stack.launch.subprocess, "run"),
                    mock.patch.object(kbn_stack.launch, "run_detached", return_value=0) as run_detached,
                    contextlib.redirect_stdout(io.StringIO()) as output,
                ):
                    assert kbn_stack.main(["--detach", *argv]) == 0
            return registry[worktree], run_detached.call_args, probe, output.getvalue()

    def test_main_isolates_when_the_branch_changes_saved_object_definitions(self):
        kbn_stack = _load_kbn_stack_command()
        signal = "x-pack/platform/plugins/shared/alerting/server/saved_objects/index.ts"
        entry, call, probe, output = self._start_with_signals(kbn_stack, [], [signal])
        probe.assert_called_once()
        assert call.kwargs["shared"] is None
        assert "es_key" not in entry
        assert entry["slot"] == 1  # the shared ES keeps slot 0
        assert signal in output and "starting an isolated ES" in output and "--share-es" in output

    def test_main_share_es_attaches_without_consulting_the_diff(self):
        kbn_stack = _load_kbn_stack_command()
        entry, call, probe, _ = self._start_with_signals(
            kbn_stack, ["--share-es"], ["would/be/ignored/server/saved_objects/x.ts"]
        )
        probe.assert_not_called()
        assert call.kwargs["shared"]["create"] is False
        assert entry["es_key"] == "9.6.0"

    def test_main_share_es_warns_when_flags_already_force_an_isolated_es(self):
        kbn_stack = _load_kbn_stack_command()
        entry, call, probe, output = self._start_with_signals(kbn_stack, ["--share-es", "-E", "k=v"], [])
        probe.assert_not_called()
        assert call.kwargs["shared"] is None
        assert "es_key" not in entry
        assert "--share-es has no effect here" in output

    def test_kill_pid_group_spares_the_launcher_when_the_target_shares_its_group(self):
        kbn_stack = _load_kbn_stack_command()
        # An interactive ES is spawned without start_new_session, so it shares the
        # launcher's group; stopping it on an expired trial must not killpg ourselves.
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            assert os.getpgid(child.pid) == os.getpgid(0)
            with mock.patch.object(kbn_stack.config, "KILL_GRACE_SECONDS", 3.0):
                kbn_stack.procs.kill_pid_group(child.pid)
            assert child.wait(timeout=5) != 0
        finally:
            if child.poll() is None:
                child.kill()


if __name__ == "__main__":
    unittest.main()
