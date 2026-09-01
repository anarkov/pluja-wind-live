"""Pure ICON-EU LIVE candidate selection shared by the producer and tests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

MAX_PAST_SECONDS = 2 * 60 * 60
MAX_FUTURE_SECONDS = 90 * 60


@dataclass(frozen=True)
class CompleteField:
    run: str
    forecast_hour: int
    valid: datetime
    u_url: str
    v_url: str
    t_url: str


def select_nearest_usable(candidates: list[CompleteField], now: datetime) -> CompleteField:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    usable = [candidate for candidate in candidates if -MAX_PAST_SECONDS <= (candidate.valid - now).total_seconds() <= MAX_FUTURE_SECONDS]
    if not usable:
        raise RuntimeError("No complete ICON-EU U_10M/V_10M/T_2M field is within -2h/+90m of NOW UTC")
    # Closest valid time wins; for an exact tie use the future field so the
    # publication remains useful for longer after the workflow completes.
    return min(usable, key=lambda candidate: (abs((candidate.valid - now).total_seconds()), candidate.valid < now, -candidate.valid.timestamp()))
