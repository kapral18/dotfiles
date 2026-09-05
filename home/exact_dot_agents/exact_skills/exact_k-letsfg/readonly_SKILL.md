---
name: k-letsfg
description: "Use when searching flights, fares, routes, airlines, dates, or prices with LetsFG connectors."
tool_version: "letsfg 2026.4.66 (uv tool; --version unavailable); playwriter 0.1.0 fallback"
---

# LetsFG

## Boundaries

- Book, unlock, attach payment, or register only when the user explicitly asks and confirms the real-money or account side effect.
- Use this skill instead of MCP for LetsFG; it exists to keep LetsFG tools out of every agent session.
- Prefer the local CLI over the hosted `letsfg.co` website API.
  Hosted book pages hide booking links behind the website unlock/pay/share flow.
- Open airline/OTA booking URLs only when the user asks.
  Opening is read-only, but checkout, passenger entry, payment, or final booking can create real-world side effects.
- Do not start a host browser or Playwriter for search-only tasks.
  Use `,letsfg-docker`; its connector browsers stay inside the virtual display.

## First Actions

1. Verify the local CLI is available.
   If missing, install it with the repo-managed uv tools workflow (`uv tool install letsfg` for an immediate local session;
   persistent source is `home/readonly_dot_default-uv-tools.tmpl`):

```bash
command -v letsfg
letsfg --help
letsfg search --help
```

1. For a known one-way or round-trip date, use the docker wrapper for full connector coverage without visible local browser windows:

```bash
,letsfg-docker search AMS EVN 2026-05-13 --mode fast --limit 10 --json --max-browsers 2
```

Use `--return YYYY-MM-DD` for round trips, `--currency EUR` when the user specifies currency, `--direct` for direct-only, and `--cabin M|W|C|F` for cabin class.

1. For nearby, soon, cheapest-date, or flexible-date requests, search dates through the docker wrapper and rank the returned offers.
   Default to the next 14 days from today when the user gives no range.
   The ready-to-run script (concurrent per-date `,letsfg-docker search` + price/date ranking) lives in `~/.agents/skills/k-letsfg/references/flexible-date-search.md`.

2. Use Playwriter only when rendered UI is required, such as visual checks or investigating a website regression.
   Before starting the browser fallback, read and follow `~/.agents/skills/k-letsfg/references/browser-fallback.md` in full.

## Search Rules

- Resolve route names to IATA codes before searching. Use `letsfg locations <query>` when needed.
- Prefer structured CLI arguments when origin, destination, and date are known.
- For nearby, soon, cheapest-date, or flexible-date requests, search a date range concurrently and rank by useful criteria.
  Default range: next 14 days.
- For round trips, pass `--return YYYY-MM-DD`.
- Use `--currency` when the user specifies a currency.
- Use `--cabin` only when the user requests economy, premium economy, business, or first.
- Use `--direct` or `--max-stops 0` only when the user asks for direct flights.
- Use `,letsfg-docker` instead of `letsfg` directly.
  This runs the CLI in a Docker container with Xvfb, avoiding visible local Chrome windows while keeping all browser-based connectors active.
- Prefer `--mode fast` for interactive searches.
  Use the default full search only when the user wants maximum coverage and accepts a slower run.
- Prefer direct `booking_url` fields returned by local results. Do not create LetsFG hosted `/book/...` URLs.
- Summarize price, airline, route, departure/arrival, duration, stops, source, and direct booking URL when available.

## Safety

- Search is read-only and free.
- Opening airline/OTA result pages is still read-only, but checkout, account registration, passenger entry, payment setup, or final booking can create account, payment, booking, or external state.
  Ask for explicit confirmation before running any of them.
- `letsfg unlock`, `letsfg book`, `letsfg register`, `letsfg star`, and `letsfg setup-payment` call the LetsFG backend or payment/account flows.
  Run them only when the user explicitly requests that side effect.
- For booking, passenger names must match passport/government ID exactly. Use only user-provided passenger details, never invented ones.

## Runtime Notes

- The local CLI is installed as a uv tool from `home/readonly_dot_default-uv-tools.tmpl`.
- `letsfg --version` is not implemented.
  Verify version from uv install output or `uv tool list`; the audited version is `letsfg==2026.4.66`.
- `LETSFG_BROWSERS=0` is the supported way to prevent browser connector launches. The CLI has no `--headless` flag.
- Local `letsfg search ... --json` returns offers with `booking_url`, `source_tier`, and `is_locked`.
  Local free search should return `source_tier: "free"` and `is_locked: false` for directly usable result links.
- Some LetsFG connectors hard-code headed Chrome or CDP Chrome because their target sites block headless browsers.
  Do not patch installed package files in-place.
  Use `,letsfg-docker` to keep those connectors inside the virtual display; rendered-UI Playwriter work still requires the browser-fallback trigger.
- The system Python may not import `letsfg` because uv tools live in isolated environments.
  Prefer the `letsfg` executable instead of Python imports.
- Before using the rendered-UI browser launcher, read and follow `~/.agents/skills/k-letsfg/references/browser-fallback.md` in full.

## Output

- Return a concise ranked list of useful options and include the exact command or script path used.
- Include the searched date range for flexible-date searches.
- Include direct booking URLs when local results provide them.
- If a command fails, include the failure and the smallest next verification step.
