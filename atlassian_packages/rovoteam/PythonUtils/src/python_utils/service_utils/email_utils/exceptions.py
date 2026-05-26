"""
Email Utils Exceptions

Custom exception classes for email operations.
"""


class EmailAuthenticationError(Exception):
    """Raised when email authentication fails."""
    pass


class EmailRateLimitError(Exception):
    """Raised when email service rate limits are exceeded."""
    pass


class EmailNetworkError(Exception):
    """Raised when network errors occur during email operations."""
    pass


class EmailAPIError(Exception):
    """Raised when email API returns an error."""
    pass
