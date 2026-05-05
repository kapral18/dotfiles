---
name: letsfg
description: Search flight tickets with the local LetsFG CLI connectors, returning free local results and direct booking URLs. Use when the user asks for flights, fares, airline tickets, routes, dates, or travel-price search via LetsFG.
tool_version: "letsfg 2026.4.66 (uv tool; --version unavailable); playwriter 0.1.0 fallback"
---

# LetsFG

## Use When

- The user asks to search flight tickets, fares, routes, or airline options.
- The user mentions LetsFG or wants flight-search results from the agent.

## Do Not Use

- Do not book, unlock, attach payment, or register unless the user explicitly asks and confirms the real-money or account side effect.
- Do not use MCP for LetsFG; this skill exists to avoid injecting LetsFG tools into every agent session.
- Do not use the hosted `letsfg.co` website API by default. Hosted book pages hide booking links behind the website unlock/pay/share flow.
- Do not open airline/OTA booking URLs unless the user asks. Opening is read-only, but checkout, passenger entry, payment, or final booking can create real-world side effects.
- Do not start a browser for search-only tasks. Use the local `letsfg` CLI first.

## First Actions

1. Verify the local CLI is available. If missing, install it with the repo-managed uv tools workflow (`uv tool install letsfg` for an immediate local session; persistent source is `home/readonly_dot_default-uv-tools.tmpl`):

```bash
command -v letsfg
letsfg --help
letsfg search --help
```

1. For a known one-way or round-trip date, use the docker wrapper for browserless search with full coverage:

```bash
letsfg-docker search AMS EVN 2026-05-13 --mode fast --limit 10 --json --max-browsers 2
```

Use `--return YYYY-MM-DD` for round trips, `--currency EUR` when the user specifies currency, `--direct` for direct-only, and `--cabin M|W|C|F` for cabin class.

1. For nearby, soon, cheapest-date, or flexible-date requests, search dates locally without browser connectors and rank the returned offers. Default to the next 14 days from today when the user gives no range:

```bash
python3 - <<'PY'
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

origin = "AMS"
destination = "EVN"
dates = [(date.today() + timedelta(days=i)).isoformat() for i in range(14)]

def search(day):
    cmd = [
        "letsfg-docker",
        "search",
        origin,
        destination,
        day,
        "--mode",
        "fast",
        "--limit",
        "10",
        "--json",
        "--max-browsers",
        "2",
    ]
    completed = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=180,
    )
    if completed.returncode != 0:
        return day, {"error": completed.stderr.strip() or completed.stdout.strip()}
    try:
        json_start = completed.stdout.find("{")
        return day, json.loads(completed.stdout[json_start:] if json_start >= 0 else completed.stdout)
    except json.JSONDecodeError as exc:
        return day, {"error": f"invalid JSON: {exc}", "stdout": completed.stdout}

with ThreadPoolExecutor(max_workers=min(2, len(dates))) as pool:
    results = dict(pool.map(search, dates))

offers = []
for day, result in results.items():
    for offer in result.get("offers") or []:
        route = offer.get("outbound") or {}
        segments = route.get("segments") or []
        first = segments[0] if segments else {}
        last = segments[-1] if segments else {}
        offers.append({
            "date": day,
            "price": offer.get("price"),
            "currency": offer.get("currency"),
            "airlines": offer.get("airlines") or [],
            "flight_number": first.get("flight_no"),
            "departure_time": first.get("departure"),
            "arrival_time": last.get("arrival"),
            "duration_seconds": route.get("total_duration_seconds"),
            "stops": route.get("stopovers"),
            "source": offer.get("source"),
            "source_tier": offer.get("source_tier"),
            "is_locked": offer.get("is_locked"),
            "booking_url": offer.get("booking_url"),
        })

offers.sort(key=lambda offer: (
    offer.get("price") is None,
    offer.get("price") if offer.get("price") is not None else float("inf"),
    offer.get("date") or "",
))
print(json.dumps({
    "searched_dates": dates,
    "errors": {day: result["error"] for day, result in results.items() if result.get("error")},
    "top_offers": offers[:10],
}, indent=2, ensure_ascii=False))
PY
```

1. Use Playwriter only when rendered UI is required, such as visual checks or investigating a website regression. Prefer the Homebrew-managed Chrome app already present on this machine:

```bash
playwriter browser list
profile="$(mktemp -d -t playwriter-letsfg.XXXXXX)"
playwriter browser start "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --user-data-dir "$profile"
playwriter browser list
```

If `playwriter session new` reports multiple browsers, select the extension key for the browser you just started. Record the browser PID from `playwriter browser start` and kill it after the task if no longer needed.

```bash
playwriter session new --browser <extension-key>
playwriter -s <session-id> --timeout 360000 -e 'state.page = await context.newPage(); await state.page.goto("https://letsfg.co", { waitUntil: "domcontentloaded" }); console.log(await state.page.title())'
```

Use single quotes around `-e` snippets unless using a quoted heredoc, so the shell does not expand `$`, backticks, or backslashes.

## Search Rules

- Resolve route names to IATA codes before searching. Use `letsfg locations <query>` when needed.
- Prefer structured CLI arguments when origin, destination, and date are known.
- For nearby, soon, cheapest-date, or flexible-date requests, search a date range concurrently and rank by useful criteria. Default range: next 14 days.
- For round trips, pass `--return YYYY-MM-DD`.
- Use `--currency` when the user specifies a currency.
- Use `--cabin` only when the user requests economy, premium economy, business, or first.
- Use `--direct` or `--max-stops 0` only when the user asks for direct flights.
- Use `letsfg-docker` instead of `letsfg` directly. This runs the CLI in a Docker container with Xvfb, avoiding visible local Chrome windows while keeping all browser-based connectors active.
- Prefer `--mode fast` for interactive searches. Use the default full search only when the user wants maximum coverage and accepts a slower run.
- Prefer direct `booking_url` fields returned by local results. Do not create LetsFG hosted `/book/...` URLs.
- Summarize price, airline, route, departure/arrival, duration, stops, source, and direct booking URL when available.

## Safety

- Search is read-only and free.
- Opening airline/OTA result pages is still read-only, but checkout, account registration, passenger entry, payment setup, or final booking can create account, payment, booking, or external state. Ask for explicit confirmation before running any of them.
- `letsfg unlock`, `letsfg book`, `letsfg register`, `letsfg star`, and `letsfg setup-payment` call the LetsFG backend or payment/account flows. Do not run them unless the user explicitly requests that side effect.
- For booking, passenger names must match passport/government ID exactly. Never invent passenger details.

## Runtime Notes

- The local CLI is installed as a uv tool from `home/readonly_dot_default-uv-tools.tmpl`.
- `letsfg --version` is not implemented. Verify version from uv install output or `uv tool list`; the audited version is `letsfg==2026.4.66`.
- `LETSFG_BROWSERS=0` is the supported way to prevent browser connector launches. The CLI has no `--headless` flag.
- Local `letsfg search ... --json` returns offers with `booking_url`, `source_tier`, and `is_locked`. Local free search should return `source_tier: "free"` and `is_locked: false` for directly usable result links.
- Some LetsFG connectors hard-code headed Chrome or CDP Chrome because their target sites block headless browsers. Do not patch installed package files in-place; prefer browserless search by default and treat browser connectors as explicit opt-in coverage.
- The system Python may not import `letsfg` because uv tools live in isolated environments. Prefer the `letsfg` executable instead of Python imports.
- Playwriter has a hidden browser launcher: `playwriter browser start --headless`. The default browser lookup may miss `/Applications/Google Chrome.app`; pass that binary explicitly when browser fallback is needed. This keeps LetsFG out of always-loaded MCP while still allowing rendered UI automation on demand.

## Output

- Return a concise ranked list of useful options and include the exact command or script path used.
- Include the searched date range for flexible-date searches.
- Include direct booking URLs when local results provide them.
- If a command fails, include the failure and the smallest next verification step.
