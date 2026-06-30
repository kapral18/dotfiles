# LetsFG Flexible-Date Search Script

Reference for the `letsfg` skill. Load for nearby, soon, cheapest-date, or flexible-date flight search requests.

Searches a date range concurrently via `,letsfg-docker` and ranks the returned offers by price, defaulting to the next 14 days from today when the user gives no range.
Adjust `origin`, `destination`, and `dates` for the request.

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
        ",letsfg-docker",
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
