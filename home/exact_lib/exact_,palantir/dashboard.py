#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["textual>=0.80"]
# ///
"""The seeing stone: ,palantir's Textual dashboard.

One screen sees every legion — stage, attention, criteria progress — and
commands the whole operation:

  enter   attach (tmux switch-client) to the selected legion's session
  s       summon a new legion (prompt for goal)
  e       answer the selected holding legion
  y       grant a cleared_for_human legion (closes it, routes memory)
  w       send word to the selected legion's coordinator (prompt for text)
  b       banish (fail-closed; capital B forces)
  r       refresh now
  q       quit

Launched by ``,palantir`` (bare) through ``uv run`` — the PEP 723 block above
owns the textual dependency; nothing is globally installed.

``--smoke`` renders the data model once without entering the TUI loop, for
mechanical verification.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import legion_state  # noqa: E402

REFRESH_SECS = 5.0


def snapshot() -> "list[dict]":
    return legion_state.LegionState().summaries()


def run_smoke() -> int:
    # Import inside the smoke path too: the check proves textual resolves.
    from textual.app import App  # noqa: F401

    rows = snapshot()
    print(json.dumps({"palantir": "smoke", "legions": rows}, indent=2))
    return 0


def main() -> int:
    if "--smoke" in sys.argv[1:]:
        return run_smoke()

    from textual import work  # noqa: F401
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.widgets import DataTable, Footer, Header, Input, Static

    class Stone(App):
        """All legions, one glance; drill in with enter."""

        TITLE = "palantír"
        SUB_TITLE = "the stone sees all legions"
        CSS = """
        #detail { height: auto; max-height: 12; border-top: solid $accent; padding: 0 1; }
        #action-input { display: none; }
        #action-input.visible { display: block; }
        """
        BINDINGS = [
            Binding("j,down", "cursor_down", "down", key_display="j/↓"),
            Binding("k,up", "cursor_up", "up", key_display="k/↑"),
            Binding("ctrl+d,pagedown", "page_down", "page down", key_display="^D/PgDn"),
            Binding("ctrl+u,pageup", "page_up", "page up", key_display="^U/PgUp"),
            Binding("g", "cursor_top", "top"),
            Binding("G", "cursor_bottom", "bottom"),
            Binding("l", "attach", "attach"),
            Binding("home", "cursor_top", "", show=False, priority=True),
            Binding("end", "cursor_bottom", "", show=False, priority=True),
            Binding("enter", "attach", "", show=False, priority=True),
            Binding("s", "summon", "summon"),
            Binding("e", "answer", "answer"),
            Binding("y", "grant", "grant"),
            Binding("w", "send_word", "send word"),
            Binding("b", "banish", "banish"),
            Binding("B", "force_banish", "force banish", show=False),
            Binding("r", "refresh", "refresh"),
            Binding("q", "quit", "quit"),
        ]

        def compose(self) -> ComposeResult:
            yield Header()
            with Vertical():
                yield DataTable(id="legions", cursor_type="row")
                yield Static(id="detail")
                yield Input(placeholder="enter action text — enter to send, esc to cancel", id="action-input")
            yield Footer()

        def on_mount(self) -> None:
            self.palantir = str(Path.home() / "bin" / ",palantir")
            self.input_mode = ""
            self.input_legion_id = None
            table = self.query_one("#legions", DataTable)
            table.add_columns("legion", "stage", "attention", "criteria", "attempts", "goal")
            self.reload()
            self.set_interval(REFRESH_SECS, self.reload)

        def reload(self) -> None:
            table = self.query_one("#legions", DataTable)
            selected = self.selected_id()
            table.clear()
            for row in snapshot():
                attention = row.get("attention") or ""
                table.add_row(
                    row["id"],
                    row.get("stage", ""),
                    attention,
                    f"{row.get('criteria_green', 0)}/{row.get('criteria_total', 0)}",
                    str(row.get("implement_attempts", 0)),
                    (row.get("goal") or "")[:70],
                    key=row["id"],
                )
            if selected is not None:
                try:
                    table.move_cursor(row=table.get_row_index(selected))
                except Exception:
                    pass
            self.show_detail()

        def selected_id(self) -> "str | None":
            table = self.query_one("#legions", DataTable)
            if table.row_count == 0 or table.cursor_row is None:
                return None
            try:
                return str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
            except Exception:
                return None

        def show_detail(self) -> None:
            detail = self.query_one("#detail", Static)
            legion_id = self.selected_id()
            if not legion_id:
                detail.update("no legions — summon one: ,palantir summon '<goal>'")
                return
            try:
                manifest = legion_state.LegionState().load(legion_id)
            except SystemExit:
                detail.update(f"{legion_id}: manifest unreadable")
                return
            holding = manifest.get("holding") or {}
            lines = [
                f"[b]{legion_id}[/b]  {manifest.get('stage')}  session={manifest.get('session')}",
                f"worktree: {manifest.get('worktree', '')}",
            ]
            if holding:
                lines.append(f"[yellow]holding[/yellow]: {holding.get('reason')} — {holding.get('text', '')[:120]}")
            blockers = manifest.get("review_blockers") or []
            if blockers:
                lines.append(f"[red]review blockers[/red]: {len(blockers)}")
            detail.update("\n".join(lines))

        def on_data_table_row_highlighted(self, _event) -> None:
            self.show_detail()

        def _run(self, *argv: str) -> subprocess.CompletedProcess[str]:
            proc = subprocess.run(list(argv), capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                self.notify(proc.stderr.strip() or f"{argv[0]} exited {proc.returncode}", severity="error")
            return proc

        def action_refresh(self) -> None:
            self.reload()

        def action_cursor_down(self) -> None:
            self.query_one("#legions", DataTable).action_cursor_down()

        def action_cursor_up(self) -> None:
            self.query_one("#legions", DataTable).action_cursor_up()

        def action_page_down(self) -> None:
            self.query_one("#legions", DataTable).action_page_down()

        def action_page_up(self) -> None:
            self.query_one("#legions", DataTable).action_page_up()

        def action_cursor_top(self) -> None:
            table = self.query_one("#legions", DataTable)
            if table.row_count:
                table.move_cursor(row=0)

        def action_cursor_bottom(self) -> None:
            table = self.query_one("#legions", DataTable)
            if table.row_count:
                table.move_cursor(row=table.row_count - 1)

        def action_attach(self) -> None:
            legion_id = self.selected_id()
            if not legion_id:
                return
            try:
                session = legion_state.LegionState().load(legion_id).get("session", "")
            except SystemExit:
                return
            if session:
                self._run("tmux", "switch-client", "-t", f"={session}")

        def _open_input(self, mode: str, placeholder: str, legion_id: "str | None" = None) -> None:
            self.input_mode = mode
            self.input_legion_id = legion_id
            box = self.query_one("#action-input", Input)
            box.placeholder = placeholder
            box.add_class("visible")
            box.focus()

        def action_summon(self) -> None:
            self._open_input("summon", "new legion goal — enter to summon, esc to cancel")

        def action_answer(self) -> None:
            legion_id = self.selected_id()
            if legion_id:
                self._open_input("answer", "answer — enter to resume, esc to cancel", legion_id)

        def action_grant(self) -> None:
            legion_id = self.selected_id()
            if legion_id:
                self._run(self.palantir, "grant", legion_id)
                self.reload()

        def action_banish(self) -> None:
            legion_id = self.selected_id()
            if legion_id:
                self._run(self.palantir, "banish", legion_id)
                self.reload()

        def action_force_banish(self) -> None:
            legion_id = self.selected_id()
            if legion_id:
                self._run(self.palantir, "banish", legion_id, "--force")
                self.reload()

        def action_send_word(self) -> None:
            legion_id = self.selected_id()
            if legion_id:
                self._open_input("send-word", "word to send — enter to send, esc to cancel", legion_id)

        def on_input_submitted(self, event) -> None:
            box = self.query_one("#action-input", Input)
            text = event.value.strip()
            legion_id = self.input_legion_id
            if text and self.input_mode == "summon":
                self._run(self.palantir, "summon", text)
            elif text and self.input_mode == "answer" and legion_id:
                self._run(self.palantir, "answer", legion_id, text)
            elif text and self.input_mode == "send-word" and legion_id:
                self._run(self.palantir, "send-word", legion_id, text)
            box.value = ""
            box.remove_class("visible")
            self.input_mode = ""
            self.input_legion_id = None
            self.query_one("#legions", DataTable).focus()
            self.reload()

        def key_escape(self) -> None:
            box = self.query_one("#action-input", Input)
            if box.has_class("visible"):
                box.value = ""
                box.remove_class("visible")
                self.input_mode = ""
                self.input_legion_id = None
                self.query_one("#legions", DataTable).focus()

    Stone().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
