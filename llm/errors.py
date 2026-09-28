class LLMError(Exception):
    """Base class for domain errors raised while generating a recipe."""


class ModelReportedError(LLMError):
    """The model itself returned a non-null `error` field."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationFailedError(LLMError):
    """The model output could not be parsed into the strict schema, even after a retry."""


class UpstreamError(LLMError):
    """The OpenAI API call failed for a reason other than timeout or rate limiting."""


class UpstreamTimeoutError(LLMError):
    """The OpenAI API call timed out."""


class UpstreamRateLimitError(LLMError):
    """The OpenAI API call was rate limited."""
