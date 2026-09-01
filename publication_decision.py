#!/usr/bin/env python3
"""Print the only allowed D2R LIVE publication decision."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from live_selection import CompleteField, decide_publication, is_usable

def field(path: Path | None) -> CompleteField | None:
    if path is None or not path.is_file(): return None
    data = json.loads(path.read_text())
    region = data["regions"]["iberia"]; wind = region["fields"][0]; temp = region["temperatureFields"][0]
    if wind["forecastHour"] != temp["forecastHour"] or wind["validTime"] != temp["validTime"]: raise RuntimeError("wind_temperature_not_atomic")
    valid = datetime.fromisoformat(wind["validTime"].replace("Z", "+00:00")).astimezone(timezone.utc)
    return CompleteField(str(data["run"]), int(wind["forecastHour"]), valid, "", "", "")

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--candidate", type=Path); parser.add_argument("--current", type=Path); parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(); now = datetime.now(timezone.utc); current = field(args.current); candidate = field(args.candidate)
    result = decide_publication(current, candidate, now)
    payload = {"NOW_UTC": now.isoformat(), "CURRENT": None if current is None else {"run":current.run,"forecastHour":current.forecast_hour,"validTime":current.valid.isoformat(),"fresh":is_usable(current.valid,now)}, "CANDIDATE": None if candidate is None else {"run":candidate.run,"forecastHour":candidate.forecast_hour,"validTime":candidate.valid.isoformat(),"fresh":is_usable(candidate.valid,now),"completeTriplet":True}, "FINAL":{"decision":result.decision,"reason":result.reason}}
    print(json.dumps(payload, sort_keys=True))
    if args.github_output: args.github_output.write_text(f"decision={result.decision}\ncurrent_fresh={'true' if current and is_usable(current.valid, now) else 'false'}\n")
    return 1 if result.decision == "NO_VALID_CANDIDATE" and not (current and is_usable(current.valid, now)) else 0
if __name__ == "__main__": raise SystemExit(main())
