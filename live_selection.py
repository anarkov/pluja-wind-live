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


@dataclass(frozen=True)
class PublicationDecision:
    decision: str
    reason: str


def is_usable(valid: datetime, now: datetime) -> bool:
    return -MAX_PAST_SECONDS <= (valid - now).total_seconds() <= MAX_FUTURE_SECONDS


def decide_publication(current: CompleteField | None, candidate: CompleteField | None, now: datetime) -> PublicationDecision:
    """Resolve publication against the remote manifest immediately before push."""
    current_fresh = current is not None and is_usable(current.valid, now)
    candidate_fresh = candidate is not None and is_usable(candidate.valid, now)
    if not candidate_fresh:
        return PublicationDecision("NO_VALID_CANDIDATE", "current_fresh" if current_fresh else "current_stale")
    if current is None or not current_fresh:
        return PublicationDecision("PUBLISH", "candidate_fresh_current_missing_or_stale")
    if candidate.valid < current.valid:
        return PublicationDecision("REJECT_DOWNGRADE", "candidate_validTime_older_than_remote")
    if candidate.valid == current.valid:
        return PublicationDecision("KEEP_CURRENT", "same_validTime_as_remote")
    return PublicationDecision("PUBLISH", "candidate_validTime_newer_than_remote")


def select_nearest_usable(candidates: list[CompleteField], now: datetime) -> CompleteField:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    usable = [candidate for candidate in candidates if is_usable(candidate.valid, now)]
    if not usable:
        raise RuntimeError("No complete ICON-EU U_10M/V_10M/T_2M field is within -2h/+90m of NOW UTC")
    # Closest valid time wins; for an exact tie use the future field so the
    # publication remains useful for longer after the workflow completes.
    return min(usable, key=lambda candidate: (abs((candidate.valid - now).total_seconds()), candidate.valid < now, -candidate.valid.timestamp()))
