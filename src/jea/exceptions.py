"""Custom exception hierarchy for JEA."""


class JEAError(Exception):
    """Base exception for JEA."""


class EmailFetchError(JEAError):
    """Failed to fetch emails."""


class OAuthError(JEAError):
    """OAuth authentication failed."""


class ReplySendError(JEAError):
    """Failed to send reply."""


class ConfigError(JEAError):
    """Configuration error."""


class DatabaseError(JEAError):
    """Database operation failed."""


class ExtractionError(JEAError):
    """Failed to extract data from email."""


class ClassificationError(JEAError):
    """Failed to classify email."""
