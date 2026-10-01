"""Pure helpers for DWD's v1 parameter/run/step hierarchy."""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import unquote

from live_selection import CompleteField

COMPONENTS = ("U_10M", "V_10M", "T_2M")


def parse_v1_run(value: str) -> str | None:
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}%3A\d{2})/", value)
    return unquote(match.group(1)) if match else None


def parse_v1_forecast_hour(value: str) -> int | None:
    match = re.fullmatch(r"PT(\d{3})H00M\.grib2", value)
    return int(match.group(1)) if match else None


def v1_complete_candidates(available: dict[str, dict[str, set[int]]], base: str) -> list[CompleteField]:
    common_runs = set.intersection(*(set(available.get(component, {})) for component in COMPONENTS)) if all(available.get(component) for component in COMPONENTS) else set()
    candidates: list[CompleteField] = []
    for run_text in common_runs:
        hours = set.intersection(*(available[component][run_text] for component in COMPONENTS))
        run_at = dt.datetime.strptime(run_text, "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc)
        encoded_run = run_text.replace(":", "%3A")
        for forecast_hour in hours:
            step = f"PT{forecast_hour:03d}H00M.grib2"
            urls = [f"{base}/p/{component}/r/{encoded_run}/s/{step}" for component in COMPONENTS]
            candidates.append(CompleteField(run_at.strftime("%Y%m%d%H"), forecast_hour, run_at + dt.timedelta(hours=forecast_hour), *urls))
    return candidates
