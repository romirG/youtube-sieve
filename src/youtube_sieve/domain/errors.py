"""Errors raised by the domain layer."""


class DomainError(Exception):
    """Base class for every error the domain layer raises on purpose."""


class InvalidDurationError(DomainError, ValueError):
    """A duration string is malformed or cannot be converted to an exact number of seconds."""
