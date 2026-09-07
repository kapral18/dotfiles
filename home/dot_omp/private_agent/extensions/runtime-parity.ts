// Managed by chezmoi (source: home/dot_omp/private_agent/extensions/runtime-parity.ts).
// OMP runtime defaults that mirror the shared Cursor contracts.

import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent"

const SEARCH_TOOLS = ["grep", "find", "ls"]
const TOOL_SELECTION_FLAGS = ["--tools", "-t", "--exclude-tools", "-xt", "--no-tools", "-nt", "--no-builtin-tools", "-nbt"]

function hasExplicitToolSelection(argv: string[]): boolean {
  return argv.some((arg) =>
    TOOL_SELECTION_FLAGS.some((flag) => arg === flag || arg.startsWith(`${flag}=`)),
  )
}

function enableSearchTools(pi: ExtensionAPI): void {
  if (hasExplicitToolSelection(process.argv.slice(2))) return
  const active = pi.getActiveTools()
  const merged = [...active]
  for (const tool of SEARCH_TOOLS) {
    if (!merged.includes(tool)) merged.push(tool)
  }
  if (merged.length !== active.length) pi.setActiveTools(merged)
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", () => {
    enableSearchTools(pi)
  })
}
