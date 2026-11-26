"""Errors raised by the domain layer."""


class DomainError(Exception):
    """Base class for every error the domain layer raises on purpose."""


class InvalidDurationError(DomainError, ValueError):
    """A duration string is malformed or cannot be converted to an exact number of seconds."""


class InvalidSimilarityConfigError(DomainError, ValueError):
    """Similarity settings are out of range, such as a negative field weight."""


class InvalidDocumentError(DomainError, ValueError):
    """A document to compare is malformed, such as having an empty id."""


class InvalidQuotaError(DomainError, ValueError):
    """Quota input is invalid, such as a negative cost, a naive datetime or an unknown method."""
