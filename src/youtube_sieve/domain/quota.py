"""Quota arithmetic for the YouTube Data API: costs, estimates, budgets and settlement.

Implements the pure part of ADR 0001 (docs/adr/0001-enforce-quota-budget-before-api-calls.md):
a workflow's worst-case cost is estimated from the calls it plans to make, checked against
every applicable budget, and rejected before any API call if it does not fit. Storage and
atomic reservation live outside the domain layer.

Google meters two separate pools: `search.list` has its own bucket of calls per day, and
every other method draws units from a shared daily allowance. Allowances and costs are
configuration because Google says they can change.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from types import MappingProxyType
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from youtube_sieve.domain.errors import InvalidQuotaError

DEFAULT_QUOTA_TIMEZONE = "America/Los_Angeles"
# Largest page size for list methods (maxResults) and IDs per batched lookup.
MAX_RESULTS_PER_PAGE = 50


class Pool(StrEnum):
    UNITS = "units"
    SEARCH_CALLS = "search_calls"


class ApiMethod(StrEnum):
    """YouTube Data API v3 methods youtube-sieve may call, named as Google names them."""

    SEARCH_LIST = "search.list"
    VIDEOS_LIST = "videos.list"
    CHANNELS_LIST = "channels.list"
    PLAYLISTS_LIST = "playlists.list"
    PLAYLIST_ITEMS_LIST = "playlistItems.list"
    SUBSCRIPTIONS_LIST = "subscriptions.list"
    VIDEO_CATEGORIES_LIST = "videoCategories.list"
    I18N_LANGUAGES_LIST = "i18nLanguages.list"
    PLAYLISTS_INSERT = "playlists.insert"
    PLAYLIST_ITEMS_INSERT = "playlistItems.insert"


def _require_count(value: object, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InvalidQuotaError(f"{name} must be an integer >= {minimum}, got {value!r}")
    return value


@dataclass(frozen=True)
class Cost:
    """An amount of quota in each pool. Never negative."""

    units: int = 0
    search_calls: int = 0

    def __post_init__(self) -> None:
        _require_count(self.units, "units")
        _require_count(self.search_calls, "search_calls")

    @property
    def is_zero(self) -> bool:
        return self.units == 0 and self.search_calls == 0

    def amount(self, pool: Pool) -> int:
        return self.units if pool is Pool.UNITS else self.search_calls

    def __add__(self, other: Cost) -> Cost:
        return Cost(self.units + other.units, self.search_calls + other.search_calls)

    def __mul__(self, factor: object) -> Cost:
        if isinstance(factor, bool | float):
            raise InvalidQuotaError(f"a cost can only be scaled by an integer, got {factor!r}")
        if not isinstance(factor, int):
            return NotImplemented
        _require_count(factor, "scale factor")
        return Cost(self.units * factor, self.search_calls * factor)

    __rmul__ = __mul__

    def saturating_sub(self, other: Cost) -> Cost:
        """This cost minus another, with each pool floored at zero."""
        return Cost(
            max(0, self.units - other.units), max(0, self.search_calls - other.search_calls)
        )


ZERO = Cost()

# From Google's quota cost table. search.list draws on its own daily bucket of calls.
DEFAULT_COST_TABLE: Mapping[ApiMethod, Cost] = MappingProxyType(
    {
        ApiMethod.SEARCH_LIST: Cost(search_calls=1),
        ApiMethod.VIDEOS_LIST: Cost(units=1),
        ApiMethod.CHANNELS_LIST: Cost(units=1),
        ApiMethod.PLAYLISTS_LIST: Cost(units=1),
        ApiMethod.PLAYLIST_ITEMS_LIST: Cost(units=1),
        ApiMethod.SUBSCRIPTIONS_LIST: Cost(units=1),
        ApiMethod.VIDEO_CATEGORIES_LIST: Cost(units=1),
        ApiMethod.I18N_LANGUAGES_LIST: Cost(units=1),
        ApiMethod.PLAYLISTS_INSERT: Cost(units=50),
        ApiMethod.PLAYLIST_ITEMS_INSERT: Cost(units=50),
    }
)


@dataclass(frozen=True)
class PlannedCall:
    """A method a workflow may call, and the most requests (pages, batches) it may make."""

    method: ApiMethod
    requests: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.method, ApiMethod):
            raise InvalidQuotaError(f"unknown API method {self.method!r}")
        _require_count(self.requests, "requests", minimum=1)


def estimate(
    plan: Iterable[PlannedCall], table: Mapping[ApiMethod, Cost] = DEFAULT_COST_TABLE
) -> Cost:
    """Worst-case cost of a plan. Every request is charged, including extra pages."""
    total = ZERO
    for call in plan:
        if call.method not in table:
            raise InvalidQuotaError(f"no quota cost configured for {call.method.value}")
        total = total + table[call.method] * call.requests
    return total


def requests_needed(items: int, per_request: int = MAX_RESULTS_PER_PAGE) -> int:
    """Requests needed to fetch or send `items` when each request handles `per_request`."""
    _require_count(items, "items")
    _require_count(per_request, "per_request", minimum=1)
    return math.ceil(items / per_request)


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidQuotaError(f"unknown time zone {tz!r}") from exc


def _require_aware(now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise InvalidQuotaError("datetime must include a time zone")


def quota_day(now: datetime, tz: str = DEFAULT_QUOTA_TIMEZONE) -> date:
    """The quota day `now` falls in: the calendar date in the quota time zone."""
    _require_aware(now)
    return now.astimezone(_zone(tz)).date()


def next_reset(now: datetime, tz: str = DEFAULT_QUOTA_TIMEZONE) -> datetime:
    """The next midnight in the quota time zone, strictly after `now`."""
    _require_aware(now)
    zone = _zone(tz)
    return datetime.combine(quota_day(now, tz) + timedelta(days=1), time.min, tzinfo=zone)


@dataclass(frozen=True)
class BudgetState:
    """One budget's limit, what has been used or reserved, and pools Google has exhausted."""

    name: str
    limit: Cost
    used: Cost = ZERO
    exhausted: frozenset[Pool] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidQuotaError("a budget needs a name")
        if not all(isinstance(pool, Pool) for pool in self.exhausted):
            raise InvalidQuotaError(f"unknown pool in exhausted: {set(self.exhausted)!r}")

    @property
    def remaining(self) -> Cost:
        return self.limit.saturating_sub(self.used)

    def available(self, pool: Pool) -> int:
        return 0 if pool in self.exhausted else self.remaining.amount(pool)


@dataclass(frozen=True)
class Shortfall:
    budget: str
    pool: Pool
    needed: int
    remaining: int


@dataclass(frozen=True)
class QuotaDecision:
    shortfalls: tuple[Shortfall, ...] = ()

    @property
    def allowed(self) -> bool:
        return not self.shortfalls


def check_budgets(cost: Cost, budgets: Iterable[BudgetState]) -> QuotaDecision:
    """Allow `cost` only if it fits every budget in every pool it uses; list all shortfalls."""
    states = list(budgets)
    if not states:
        raise InvalidQuotaError("a request must be checked against at least one budget")
    shortfalls = tuple(
        Shortfall(state.name, pool, cost.amount(pool), state.available(pool))
        for state in states
        for pool in Pool
        if cost.amount(pool) > state.available(pool)
    )
    return QuotaDecision(shortfalls)


@dataclass(frozen=True)
class Settlement:
    release: Cost
    overrun: Cost

    @property
    def undercounted(self) -> bool:
        """True if actual use exceeded the reservation, meaning the estimate was too low."""
        return not self.overrun.is_zero


def settle(reserved: Cost, actual: Cost) -> Settlement:
    """Compare a reservation with actual use: what to release, and any overrun."""
    return Settlement(
        release=reserved.saturating_sub(actual), overrun=actual.saturating_sub(reserved)
    )
