"""Unit tests for youtube_sieve.domain.durations."""

import pytest

from youtube_sieve.domain.durations import parse_duration
from youtube_sieve.domain.errors import DomainError, InvalidDurationError

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR


# --- Valid durations -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        # Forms documented for contentDetails.duration
        ("PT15M33S", 15 * MINUTE + 33),
        ("PT1H2M10S", HOUR + 2 * MINUTE + 10),
        ("P1DT2H3M4S", DAY + 2 * HOUR + 3 * MINUTE + 4),
        # Any subset of components
        ("PT45S", 45),
        ("PT7M", 7 * MINUTE),
        ("PT3H", 3 * HOUR),
        ("P2D", 2 * DAY),
        ("PT1H30S", HOUR + 30),
        ("P1DT5M", DAY + 5 * MINUTE),
        ("P1DT30S", DAY + 30),
        ("PT2H5M", 2 * HOUR + 5 * MINUTE),
    ],
)
def test_parses_valid_durations(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["P0D", "PT0S", "PT0M", "PT0H0M0S", "P0DT0H"])
def test_zero_durations_parse_to_zero(text):
    assert parse_duration(text) == 0


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("PT90S", 90),
        ("PT75M", 75 * MINUTE),
        ("PT36H", 36 * HOUR),
    ],
)
def test_components_are_not_limited_to_their_usual_range(text, seconds):
    assert parse_duration(text) == seconds


def test_leading_zeros_are_accepted():
    assert parse_duration("PT01M05S") == MINUTE + 5


def test_very_large_values_are_exact():
    assert parse_duration("P10000DT23H59M59S") == 10000 * DAY + DAY - 1


def test_result_is_an_int():
    assert type(parse_duration("PT1M")) is int


# --- Invalid durations ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "empty"),
        ("P", "no components"),
        ("PT", "no components"),
        ("P1DT", "T without time"),
        ("T5M", "missing P"),
        ("5M", "missing P"),
        ("PT5M3", "trailing number"),
        ("PT5", "number without designator"),
        ("PTM", "designator without number"),
        ("PT5S3M", "wrong order"),
        ("PT1M1H", "wrong order"),
        ("P1HT", "time designator before T"),
        ("PT5M5M", "repeated designator"),
        ("P1D1D", "repeated designator"),
        ("PT5X", "unknown designator"),
        ("P1W", "weeks are not used by YouTube"),
        ("pt5m", "lower case"),
        ("Pt5M", "lower case"),
        (" PT5M", "leading whitespace"),
        ("PT5M ", "trailing whitespace"),
        ("PT5M\n", "trailing newline"),
        ("P T5M", "inner whitespace"),
        ("-PT5M", "negative sign"),
        ("PT-5M", "negative number"),
        ("PT+5M", "plus sign"),
        ("PT1.5S", "decimal"),
        ("PT1,5S", "decimal comma"),
        ("PT\uff11M", "non-ASCII digit (full-width 1)"),
    ],
)
def test_malformed_durations_are_rejected(text, reason):
    with pytest.raises(InvalidDurationError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["P1Y", "P2M", "P1Y2M3DT4H", "P1MT5M"])
def test_years_and_months_are_rejected_as_inexact(text):
    with pytest.raises(InvalidDurationError, match="years and months"):
        parse_duration(text)


@pytest.mark.parametrize("value", [None, 930, 15.5, b"PT15M33S", ["PT1M"]])
def test_non_string_input_is_rejected(value):
    with pytest.raises(InvalidDurationError, match="text"):
        parse_duration(value)


def test_error_message_names_the_input():
    with pytest.raises(InvalidDurationError, match="'PT5X'"):
        parse_duration("PT5X")


def test_error_is_a_domain_error_and_a_value_error():
    with pytest.raises(DomainError):
        parse_duration("nonsense")
    with pytest.raises(ValueError):
        parse_duration("nonsense")


def test_overlong_input_is_rejected_without_echoing_it_in_full():
    text = "PT" + "9" * 10_000 + "S"
    with pytest.raises(InvalidDurationError) as caught:
        parse_duration(text)
    assert len(str(caught.value)) < 200
