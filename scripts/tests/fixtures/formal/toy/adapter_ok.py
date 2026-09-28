#!/usr/bin/env python3
"""``,formal replay`` adapter: a faithful Python reimplementation of the toy fixture machine.

Reads ``FORMAL_TRACES`` (JSONL -- ``,formal traces``' own output shape: one
``{"trace_id","init","init_obs","steps":[{"event","expect"}]}`` per line) and writes
``FORMAL_OUT`` (JSONL: one ``{"trace_id","steps":[{"observed":obs}]}`` per line, one "observed"
entry per input step, walked chronologically from ``init_obs``) -- the exact shape
``,formal replay`` compares field-by-field against each step's ``expect``.
"""

import json
import os


def step(state, event):
    phase = state["phase"]
    recorded = state["recorded"]
    name = event["name"]
    args = event.get("args", {})
    if name == "start" and phase == "idle":
        return {"phase": "running", "recorded": recorded}
    if name == "finish" and phase == "running":
        if args.get("ok"):
            return {"phase": "done", "recorded": True}
        return {"phase": "idle", "recorded": recorded}
    if name == "cancel" and phase == "running":
        return {"phase": "idle", "recorded": True}
    if name == "reset" and phase == "done":
        return {"phase": "idle", "recorded": False}
    return {"phase": phase, "recorded": recorded}


def main():
    traces_path = os.environ["FORMAL_TRACES"]
    out_path = os.environ["FORMAL_OUT"]
    with open(traces_path, encoding="utf-8") as traces_file, open(out_path, "w", encoding="utf-8") as out_file:
        for line in traces_file:
            line = line.strip()
            if not line:
                continue
            trace = json.loads(line)
            state = dict(trace["init_obs"])
            observed_steps = []
            for one_step in trace["steps"]:
                state = step(state, one_step["event"])
                observed_steps.append({"observed": state})
            out_file.write(json.dumps({"trace_id": trace["trace_id"], "steps": observed_steps}) + "\n")


if __name__ == "__main__":
    main()
