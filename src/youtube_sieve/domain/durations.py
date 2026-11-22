"""Parse the ISO 8601 durations that the YouTube Data API returns for video length.

`videos.list` reports `contentDetails.duration` as `PT#M#S`, `PT#H#M#S`, or `P#DT#H#M#S` for
videos at least a day long. Any subset of the day, hour, minute and second components may
appear. Years and months are valid ISO 8601 but have no fixed length in seconds, so they are
rejected rather than approximated.
"""

from __future__ import annotations

import re

from youtube_sieve.domain.errors import InvalidDurationError

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR

# Durations are untrusted input; anything longer than this is not a real video length.
MAX_DURATION_LENGTH = 64
# How much of a rejected input to echo back in an error message.
MAX_ECHO_LENGTH = 40

# [0-9] rather than \d, so non-ASCII digits are rejected.
_DURATION_RE = re.compile(
    r"P"
    r"(?:(?P<years>[0-9]+)Y)?"
    r"(?:(?P<months>[0-9]+)M)?"
    r"(?:(?P<days>[0-9]+)D)?"
    r"(?P<time>T"
    r"(?:(?P<hours>[0-9]+)H)?"
    r"(?:(?P<minutes>[0-9]+)M)?"
    r"(?:(?P<seconds>[0-9]+)S)?"
    r")?"
)
_UNIT_SECONDS = {
    "days": SECONDS_PER_DAY,
    "hours": SECONDS_PER_HOUR,
    "minutes": SECONDS_PER_MINUTE,
    "seconds": 1,
}
_TIME_UNITS = ("hours", "minutes", "seconds")


def _shown(text: str) -> str:
    """The input as it appears in error messages, shortened if it is long."""
    if len(text) <= MAX_ECHO_LENGTH:
        return repr(text)
    return repr(text[:MAX_ECHO_LENGTH]) + f"… ({len(text)} characters)"


def parse_duration(text: str) -> int:
    """Return the number of whole seconds in an ISO 8601 duration such as ``PT15M33S``.

    Raises:
        InvalidDurationError: if ``text`` is not a string, is malformed, or uses years or
            months, which cannot be converted to an exact number of seconds.
    """
    if not isinstance(text, str):
        raise InvalidDurationError(f"duration must be text, got {type(text).__name__}")
    if len(text) > MAX_DURATION_LENGTH:
        raise InvalidDurationError(f"duration {_shown(text)} is too long to be a video length")

    match = _DURATION_RE.fullmatch(text)
    if match is None:
        raise InvalidDurationError(f"duration {_shown(text)} is not a valid ISO 8601 duration")
    parts = match.groupdict()
    if parts["years"] is not None or parts["months"] is not None:
        raise InvalidDurationError(
            f"duration {_shown(text)} uses years and months, which have no fixed length"
        )
    if parts["time"] is not None and all(parts[unit] is None for unit in _TIME_UNITS):
        raise InvalidDurationError(f"duration {_shown(text)} has 'T' but no time components")
    if all(parts[unit] is None for unit in _UNIT_SECONDS):
        raise InvalidDurationError(f"duration {_shown(text)} has no components")

    return sum(int(parts[unit]) * factor for unit, factor in _UNIT_SECONDS.items() if parts[unit])
