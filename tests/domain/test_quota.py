"""Unit tests for youtube_sieve.domain.quota."""

from datetime import UTC, date, datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from youtube_sieve.domain.errors import DomainError, InvalidQuotaError
from youtube_sieve.domain.quota import (
    DEFAULT_COST_TABLE,
    DEFAULT_QUOTA_TIMEZONE,
    ZERO,
    ApiMethod,
    BudgetState,
    Cost,
    PlannedCall,
    Pool,
    Shortfall,
    check_budgets,
    estimate,
    next_reset,
    quota_day,
    requests_needed,
    settle,
)

# --- Cost -----------------------------------------------------------------------------------


def test_cost_defaults_to_zero():
    assert Cost() == Cost(0, 0) and Cost().is_zero


def test_cost_addition_and_scaling():
    assert Cost(1, 2) + Cost(3, 4) == Cost(4, 6)
    assert Cost(50, 1) * 3 == Cost(150, 3)
    assert 3 * Cost(50, 1) == Cost(150, 3)
    assert Cost(50, 1) * 0 == Cost()


def test_cost_amount_by_pool():
    cost = Cost(units=7, search_calls=2)
    assert cost.amount(Pool.UNITS) == 7 and cost.amount(Pool.SEARCH_CALLS) == 2


def test_saturating_subtraction_never_goes_negative():
    assert Cost(10, 1).saturating_sub(Cost(3, 5)) == Cost(7, 0)


@pytest.mark.parametrize(
    ("units", "search_calls"), [(-1, 0), (0, -1), (1.5, 0), (True, 0), ("1", 0)]
)
def test_cost_rejects_negative_or_non_integer_amounts(units, search_calls):
    with pytest.raises(InvalidQuotaError):
        Cost(units, search_calls)


@pytest.mark.parametrize("factor", [-1, 1.5, True])
def test_cost_rejects_invalid_scaling(factor):
    with pytest.raises(InvalidQuotaError):
        Cost(1, 1) * factor


def test_cost_scaling_by_non_number_is_not_supported():
    with pytest.raises(TypeError):
        Cost(1, 1) * "2"


# --- Cost table -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "cost"),
    [
        (ApiMethod.SEARCH_LIST, Cost(units=0, search_calls=1)),
        (ApiMethod.VIDEOS_LIST, Cost(units=1)),
        (ApiMethod.CHANNELS_LIST, Cost(units=1)),
        (ApiMethod.PLAYLISTS_LIST, Cost(units=1)),
        (ApiMethod.PLAYLIST_ITEMS_LIST, Cost(units=1)),
        (ApiMethod.SUBSCRIPTIONS_LIST, Cost(units=1)),
        (ApiMethod.VIDEO_CATEGORIES_LIST, Cost(units=1)),
        (ApiMethod.I18N_LANGUAGES_LIST, Cost(units=1)),
        (ApiMethod.PLAYLISTS_INSERT, Cost(units=50)),
        (ApiMethod.PLAYLIST_ITEMS_INSERT, Cost(units=50)),
    ],
)
def test_default_cost_table_matches_googles_published_costs(method, cost):
    assert DEFAULT_COST_TABLE[method] == cost


def test_default_cost_table_covers_every_method_and_is_read_only():
    assert set(DEFAULT_COST_TABLE) == set(ApiMethod)
    with pytest.raises(TypeError):
        DEFAULT_COST_TABLE[ApiMethod.VIDEOS_LIST] = Cost(units=2)


def test_api_method_values_are_the_official_method_names():
    assert ApiMethod.PLAYLIST_ITEMS_INSERT.value == "playlistItems.insert"


# --- Estimates ------------------------------------------------------------------------------


def test_empty_plan_costs_nothing():
    assert estimate([]) == Cost()


def test_estimate_sums_planned_calls():
    plan = [
        PlannedCall(ApiMethod.SEARCH_LIST, requests=2),
        PlannedCall(ApiMethod.VIDEOS_LIST, requests=3),
    ]
    assert estimate(plan) == Cost(units=3, search_calls=2)


def test_playlist_write_costs_fifty_plus_fifty_per_video():
    videos = 20
    plan = [
        PlannedCall(ApiMethod.PLAYLISTS_INSERT),
        PlannedCall(ApiMethod.PLAYLIST_ITEMS_INSERT, requests=videos),
    ]
    assert estimate(plan) == Cost(units=50 + 50 * videos)


def test_estimate_uses_a_custom_cost_table():
    table = MappingProxyType({**DEFAULT_COST_TABLE, ApiMethod.VIDEOS_LIST: Cost(units=5)})
    assert estimate([PlannedCall(ApiMethod.VIDEOS_LIST, requests=2)], table) == Cost(units=10)


def test_estimate_rejects_methods_missing_from_the_table():
    table = {ApiMethod.VIDEOS_LIST: Cost(units=1)}
    with pytest.raises(InvalidQuotaError, match=r"search\.list"):
        estimate([PlannedCall(ApiMethod.SEARCH_LIST)], table)


def test_estimate_accepts_any_iterable():
    plan = (PlannedCall(ApiMethod.VIDEOS_LIST) for _ in range(3))
    assert estimate(plan) == Cost(units=3)


@pytest.mark.parametrize("requests", [0, -1, 1.0, True])
def test_planned_call_requires_a_positive_integer_request_count(requests):
    with pytest.raises(InvalidQuotaError):
        PlannedCall(ApiMethod.VIDEOS_LIST, requests=requests)


def test_planned_call_requires_a_known_method():
    with pytest.raises(InvalidQuotaError):
        PlannedCall("videos.list", requests=1)


@pytest.mark.parametrize(
    ("items", "per_request", "expected"),
    [(0, 50, 0), (1, 50, 1), (50, 50, 1), (51, 50, 2), (100, 50, 2), (101, 50, 3), (7, 1, 7)],
)
def test_requests_needed_rounds_up(items, per_request, expected):
    assert requests_needed(items, per_request) == expected


@pytest.mark.parametrize(
    ("items", "per_request"), [(-1, 50), (10, 0), (10, -5), (1.5, 50), (10, 2.0)]
)
def test_requests_needed_rejects_invalid_input(items, per_request):
    with pytest.raises(InvalidQuotaError):
        requests_needed(items, per_request)


# --- Quota day and reset --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("utc", "expected"),
    [
        # Pacific Standard Time, UTC-8
        (datetime(2026, 11, 22, 7, 59, 59, tzinfo=UTC), date(2026, 11, 21)),
        (datetime(2026, 11, 22, 8, 0, 0, tzinfo=UTC), date(2026, 11, 22)),
        # Pacific Daylight Time, UTC-7
        (datetime(2026, 7, 1, 6, 59, 59, tzinfo=UTC), date(2026, 6, 30)),
        (datetime(2026, 7, 1, 7, 0, 0, tzinfo=UTC), date(2026, 7, 1)),
    ],
)
def test_quota_day_follows_pacific_midnight_across_daylight_saving(utc, expected):
    assert quota_day(utc) == expected


def test_quota_day_accepts_any_aware_datetime():
    india = timezone(timedelta(hours=5, minutes=30))
    assert quota_day(datetime(2026, 11, 22, 13, 0, tzinfo=india)) == date(2026, 11, 21)


def test_quota_day_uses_a_configured_time_zone():
    now = datetime(2026, 11, 22, 3, 0, tzinfo=UTC)
    assert quota_day(now, "Asia/Kolkata") == date(2026, 11, 22)
    assert quota_day(now, DEFAULT_QUOTA_TIMEZONE) == date(2026, 11, 21)


@pytest.mark.parametrize(
    ("utc", "expected_utc"),
    [
        (datetime(2026, 11, 22, 12, 0, tzinfo=UTC), datetime(2026, 11, 23, 8, 0, tzinfo=UTC)),
        (datetime(2026, 11, 22, 7, 59, tzinfo=UTC), datetime(2026, 11, 22, 8, 0, tzinfo=UTC)),
        # Day before daylight saving starts (8 March 2026) and ends (1 November 2026)
        (datetime(2026, 3, 7, 12, 0, tzinfo=UTC), datetime(2026, 3, 8, 8, 0, tzinfo=UTC)),
        (datetime(2026, 10, 31, 12, 0, tzinfo=UTC), datetime(2026, 11, 1, 7, 0, tzinfo=UTC)),
    ],
)
def test_next_reset_is_the_next_local_midnight(utc, expected_utc):
    reset = next_reset(utc)
    assert reset == expected_utc and reset.tzinfo is not None


def test_next_reset_is_always_in_the_future():
    midnight = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)  # exactly midnight Pacific
    assert next_reset(midnight) == midnight + timedelta(days=1)


@pytest.mark.parametrize("function", [quota_day, next_reset])
def test_naive_datetimes_are_rejected(function):
    with pytest.raises(InvalidQuotaError, match="time zone"):
        function(datetime(2026, 11, 22, 12, 0))


@pytest.mark.parametrize("function", [quota_day, next_reset])
def test_unknown_time_zone_is_rejected(function):
    with pytest.raises(InvalidQuotaError, match="Mars/Olympus"):
        function(datetime(2026, 11, 22, tzinfo=UTC), "Mars/Olympus")


# --- Budget checks --------------------------------------------------------------------------


def budget(name="global", units=10_000, searches=100, used=ZERO, exhausted=frozenset()):
    return BudgetState(name, Cost(units, searches), used, frozenset(exhausted))


def test_request_within_budget_is_allowed():
    decision = check_budgets(Cost(units=100, search_calls=1), [budget()])
    assert decision.allowed and decision.shortfalls == ()


def test_request_using_exactly_the_remainder_is_allowed():
    decision = check_budgets(Cost(units=100), [budget(units=1000, used=Cost(units=900))])
    assert decision.allowed


def test_request_one_over_the_remainder_is_rejected_with_details():
    decision = check_budgets(Cost(units=101), [budget(units=1000, used=Cost(units=900))])
    assert not decision.allowed
    assert decision.shortfalls == (Shortfall("global", Pool.UNITS, needed=101, remaining=100),)


def test_search_pool_is_checked_separately_from_units():
    state = budget(units=10_000, searches=100, used=Cost(units=0, search_calls=100))
    decision = check_budgets(Cost(units=1, search_calls=1), [state])
    assert decision.shortfalls == (Shortfall("global", Pool.SEARCH_CALLS, needed=1, remaining=0),)


def test_every_applicable_budget_must_have_room():
    budgets = [budget("global"), budget("user:alice", units=2500, used=Cost(units=2000))]
    decision = check_budgets(Cost(units=600), budgets)
    assert [s.budget for s in decision.shortfalls] == ["user:alice"]


def test_all_shortfalls_are_reported():
    budgets = [
        budget("global", units=100, searches=1, used=Cost(100, 1)),
        budget("public", units=50, searches=0),
    ]
    decision = check_budgets(Cost(units=10, search_calls=1), budgets)
    assert {(s.budget, s.pool) for s in decision.shortfalls} == {
        ("global", Pool.UNITS),
        ("global", Pool.SEARCH_CALLS),
        ("public", Pool.SEARCH_CALLS),
    }


def test_overspent_budget_reports_zero_remaining():
    decision = check_budgets(Cost(units=1), [budget(units=100, used=Cost(units=150))])
    assert decision.shortfalls[0].remaining == 0


def test_exhausted_pool_rejects_requests_that_need_it():
    state = budget(exhausted={Pool.UNITS})
    decision = check_budgets(Cost(units=1), [state])
    assert decision.shortfalls == (Shortfall("global", Pool.UNITS, needed=1, remaining=0),)


def test_exhausted_pool_does_not_block_requests_that_do_not_use_it():
    state = budget(exhausted={Pool.SEARCH_CALLS})
    assert check_budgets(Cost(units=5), [state]).allowed


def test_zero_cost_request_is_always_allowed():
    state = budget(units=0, searches=0, exhausted={Pool.UNITS, Pool.SEARCH_CALLS})
    assert check_budgets(Cost(), [state]).allowed


def test_checking_against_no_budgets_is_an_error():
    with pytest.raises(InvalidQuotaError):
        check_budgets(Cost(units=1), [])


def test_budget_remaining_is_limit_minus_used():
    assert budget(units=1000, searches=100, used=Cost(250, 40)).remaining == Cost(750, 60)


def test_budget_requires_a_name():
    with pytest.raises(InvalidQuotaError):
        BudgetState("", Cost(1, 1), Cost())


def test_budget_rejects_unknown_exhausted_pools():
    with pytest.raises(InvalidQuotaError):
        BudgetState("global", Cost(1, 1), Cost(), frozenset({"units"}))


# --- Settlement -----------------------------------------------------------------------------


def test_unused_reservation_is_released():
    result = settle(
        reserved=Cost(units=1050, search_calls=2), actual=Cost(units=600, search_calls=2)
    )
    assert result.release == Cost(units=450) and result.overrun == Cost()


def test_exact_use_releases_nothing():
    result = settle(Cost(units=10), Cost(units=10))
    assert result.release == Cost() and result.overrun == Cost()


def test_use_beyond_reservation_is_reported_as_overrun():
    result = settle(reserved=Cost(units=10, search_calls=1), actual=Cost(units=12, search_calls=0))
    assert result.release == Cost(search_calls=1) and result.overrun == Cost(units=2)
    assert result.undercounted


def test_errors_are_domain_and_value_errors():
    assert issubclass(InvalidQuotaError, DomainError) and issubclass(InvalidQuotaError, ValueError)
