---
name: k-live-ui-windows
description: "Manual-only Windows/VirtualBox environment for live-UI verification: connects Playwriter to a Windows guest's browser over CDP through a host NAT port-forward, then verifies through the shared live-ui-runtime.md machinery."
disable-model-invocation: true
---

# Live UI Windows

The Windows/VirtualBox environment for live-UI verification.
Connects Playwriter to a Windows guest's browser running in VirtualBox over CDP through a host NAT port-forward, then verifies exactly like the local-browser flow: the same target-packet resolution, readiness stability guard, screenshot & evidence capture, and data/setup ladder from the shared runtime contract.

## Manual only — never automatic

`/agent-review`, `live-ui-review`, `/build`, and `k-ui-proof` verify the local browser only.
None of them resolve, infer, or accept a Windows/VirtualBox requirement anymore —
that entire environment-selection concept was purged from those flows and lives only here.

Load this skill only when the user explicitly asks, this turn, for Windows/VirtualBox verification.
Never infer Windows-testing intent from a PR/issue/spec hint, and never from an unrelated/ambiguous mention of the word "Windows" (e.g. a UI panel or feature literally named "Windows").
If the user wants Windows coverage alongside an in-flight `k-ui-proof` or `live-ui-review` check, add this skill to that turn's work by hand; do not wire it back into either flow's default path.

## Load first

Load `~/.agents/skills/k-agent-review/references/live-ui-runtime.md` for target-packet resolution (including the `elastic/kibana` fallback via `~/.agents/skills/k-elastic-domain/references/kibana-live-ui.md`), Playwriter preflight, the readiness stability guard, screenshot & evidence capture, the data/setup ladder, and the hard runtime constraints.
This skill adds only the guest-connection rung below, the URL translation lookup, and its own hard constraints.

Resolve the target packet and required runtime config the same way `k-ui-proof`'s ad-hoc mode does when no controller supplies them;
the oracle (an intended visual/state to match, or a base-vs-head comparison) comes from whichever check the user asked for.

## Local-also or Windows-only

Ask the user once whether to also verify the local browser (default — run both, mirroring the previous `windows_additional` behavior) or Windows-only (skip local; use only when the user says the path is Windows-exclusive).
Resolve this once per invocation; never re-decide it per finding/criterion.

## VirtualBox/CDP connection rung

Run this once per verification, before target-packet URL translation and before observation.

0. `VBoxManage --version` must succeed. If VirtualBox itself is not installed, return `Blocked` immediately — this skill never installs it.
1. Resolve the VM name. Never guess it.
   In order: an explicit name supplied this turn, then a previously confirmed name in the local registry (`~/.cache/live-ui-windows/registry.json`, keyed by VM name), then ask the user once and record the answer in that registry.
2. Read `VMState` via `VBoxManage showvminfo <vm> --machinereadable`.
   - If not `running` and the harness is shell-capable, start it with `VBoxManage startvm <vm> --type headless` (verification only needs the CDP connection, not a visible window; headless avoids popping an unwanted window on the user's screen and works on hosts with no attached display session) and wait for `running`.
     Use `--type gui` instead only when the user explicitly asked to watch/interact with the VM.
     Never change the type of an already-running VM.
   - If the harness is read-only/Ask-mode or the start fails, return `Blocked` with the exact start command.
3. Verify NIC1's attachment is `nat` (`VBoxManage showvminfo <vm> --machinereadable | grep '^nic1='`).
   VirtualBox's documented NAT gateway alias (`10.0.2.2`) is only guaranteed reachable for a NAT-attached NIC.
   If NIC1 is bridged/hostonly/other, return `Blocked` — this rung does not have a translation for other network modes.
4. Check for an existing NAT rule forwarding a host port to the guest's CDP debug port (default `9222`, or the packet-specified debug port) — `VBoxManage showvminfo <vm> | grep -i rule` and match the line whose `guest port` equals that debug port, not just the first "Rule" match (a VM can carry unrelated forwards, e.g. RDP).
   - If a matching rule exists, reuse its recorded host port.
   - If none exists, this is first-time host-side setup, not silent config rewriting:
     ask the user for approval once, naming the exact command (`VBoxManage controlvm <vm> natpf1 cdp,tcp,127.0.0.1,<hostport>,,9222`).
     On approval, add it live (VirtualBox supports adding NAT rules to a running VM) and record the host port in the registry.
     On refusal, or in a read-only/Ask-mode harness, return `Blocked` with that exact command.
5. Connect: `playwriter session new --direct localhost:<hostport>`, then smoke-test with `context.pages()`.
   - On success, continue to target-packet URL translation and navigation using this session.
     Store the page under a distinct `state` key (e.g. `state.windowsPage`); never the default `page` or another environment's page key.
   - On connection refused/timeout, the guest has no browser listening on the debug port yet —
     a one-time manual step inside Windows this skill cannot perform (Guest Additions are intentionally out of scope;
     see Hard constraints below).
     Return `Blocked` with the exact one-time instructions: launch Edge/Chrome inside Windows with `--remote-debugging-port=9222 --user-data-dir=<a dedicated profile path>`.
     Do not retry-loop the connection.
6. Once connected, every rule from the loaded `live-ui-runtime.md` contract applies unchanged to this session:
   readiness stability guard, screenshot & evidence capture, the data/setup ladder, and the hard runtime constraints.

## Target URL translation

If the resolved target packet's browser-navigation URL points at the host (e.g. `localhost`/`127.0.0.1`), the target packet owns the guest-reachable translation for that URL and any additional runtime config the backend needs to accept non-loopback connections — for `elastic/kibana`, see `~/.agents/skills/k-elastic-domain/references/kibana-live-ui.md`'s Windows/VirtualBox environment translation section.
Ask the packet for that translation; never invent one for an unfamiliar packet.
If the packet supplies no translation, return `Blocked` — do not guess a guest-facing hostname.
Scope this to URLs the browser actually navigates to; backing/data endpoints the worker calls directly stay host-facing and must not be translated.

## Hard constraints (adds to the loaded contract)

- Never install Guest Additions or otherwise modify guest OS configuration; the one-time debug-port launch inside Windows is the user's manual step, not this skill's.
- Never change an already-running VM's start type.
- This skill never controls the guest beyond VirtualBox's own host-side VM/network commands.

## Return exactly

Whatever return shape the check you're running already uses (`k-ui-proof`'s per-criterion verdicts, or `live-ui-review`'s comparison evidence), plus:

- `environment`: `windows-vbox` (and `local` too when the user chose local-also), with VM name, VM state transition, the NAT/CDP host port used, and the connection result
- the URL translation applied (source host-facing URL -> guest-facing URL) or the exact reason none was available
