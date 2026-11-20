"""Judge an account's subscription from `GET {app}/v3/users/{id}/subscriptions`.

The rules were learned live on v1 (docs/api-notes.md, "Subscriptions"):

- `primarySubscription` is absent when nothing is live, so the record list is
  read too.
- Pick the primary if present, else the newest paid (`sub_…`, `pool-seat-…`)
  record, else the newest of the rest. A lapsed purchase can sit beside a
  newer placeholder.
- Record kinds go by id prefix: `sub_…` (Stripe), `pool-seat-…` (a seat from a
  pooled plan, `provider: "pool"`, never renews; seen live 2026-11-06),
  `eight-internal-temporary-…` (never paid), `exclusive-member-…` (granted, no
  `expiresAt`).
- Judge by `expiresAt`, not `willRenew`. `willRenew` only splits a live Stripe
  record into active vs expiring.

Why id prefixes and not v3's `status` / `provider` / computed flags: the
prefixes and their meaning were seen live on many accounts; the v3 fields come
from one app capture. `provider: "eight_internal"` covers both the never-paid
placeholder and the granted membership, so it would still need `status` to
tell them apart, and nobody has seen how `status` behaves on those records.
Same amount of code, less proof. Revisit once v3 has been read live (fork
issue #14). The computed flags are returned raw so callers can use them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from dateutil import parser

ACTIVE = "active"
EXPIRING = "expiring"
LAPSED = "lapsed"
NEVER_STARTED = "never_started"
GRANTED = "granted"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

STRIPE_PREFIX = "sub_"
POOL_SEAT_PREFIX = "pool-seat-"
TEMPORARY_PREFIX = "eight-internal-temporary-"
GRANTED_PREFIX = "exclusive-member-"
PAID_PREFIXES = (STRIPE_PREFIX, POOL_SEAT_PREFIX)

COMPUTED_FLAGS = (
    "hasAccessToPremiumFeatures",
    "hasAccessToBasicFeatures",
    "hasBasic",
    "isInGracePeriod",
    "isUnpaidPremium",
    "churned",
    "cancellationReason",
    "capabilities",
    "captureStatus",
)


@dataclass
class SubscriptionState:
    """One judged state, the record it was judged on, and v3's raw flags.

    `state` is one of active, expiring, lapsed, never_started, granted,
    unknown, or unavailable (403: this token may not read that account).
    """

    state: str
    record: dict[str, Any] | None = None
    flags: dict[str, Any] = field(default_factory=dict)


def _record_id(record: dict[str, Any]) -> str:
    return str(record.get("subscriptionId") or record.get("id") or "")


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parser.isoparse(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _newest(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    return max(records, key=lambda r: _parse(r.get("createdAt")) or oldest, default=None)


def _pick(body: dict[str, Any]) -> dict[str, Any] | None:
    primary = body.get("primarySubscription")
    if isinstance(primary, dict) and primary:
        return primary
    records = [r for r in body.get("subscriptions") or [] if isinstance(r, dict)]
    paid = [r for r in records if _record_id(r).startswith(PAID_PREFIXES)]
    return _newest(paid) or _newest(records)


def _judge(record: dict[str, Any], now: datetime) -> str:
    record_id = _record_id(record)
    if record_id.startswith(GRANTED_PREFIX):
        return GRANTED
    if record_id.startswith(TEMPORARY_PREFIX):
        return NEVER_STARTED
    if not record_id.startswith(PAID_PREFIXES):
        return UNKNOWN
    expires = _parse(record.get("expiresAt"))
    if expires is None:
        return UNKNOWN
    if expires <= now:
        return LAPSED
    if record_id.startswith(POOL_SEAT_PREFIX):
        # Seats never renew (willRenew: false while live), so a live seat
        # is active, not expiring.
        return ACTIVE
    return ACTIVE if record.get("willRenew") else EXPIRING


def judge_subscription(body: Any, now: datetime | None = None) -> SubscriptionState:
    """Judge a v3 subscriptions answer."""
    if not isinstance(body, dict):
        return SubscriptionState(UNKNOWN)
    now = now or datetime.now(timezone.utc)
    flags = {key: body[key] for key in COMPUTED_FLAGS if key in body}
    record = _pick(body)
    if record is None:
        return SubscriptionState(UNKNOWN, flags=flags)
    return SubscriptionState(_judge(record, now), record=record, flags=flags)
