"""Exception hierarchy for the MangaDex SDK.

All exceptions raised by this SDK ultimately inherit from
``MangaDexApiError``, which itself inherits from the stdlib ``Exception``
class. Existing code that does ``except Exception:`` will continue to work.
"""
from __future__ import annotations

from typing import Optional

try:
	# ``requests`` is a runtime dependency of the SDK; this import is used
	# only for type hinting and to keep attribute access safe for consumers.
	from requests import Response  # type: ignore
except Exception:  # pragma: no cover - requests is always installed in practice
	Response = None  # type: ignore


class MangaDexApiError(Exception):
	"""Base class for all SDK-raised errors."""


class MangaDexHttpError(MangaDexApiError):
	"""Raised when the MangaDex API returns a non-success HTTP status.

	Attributes:
		status_code: the HTTP status code returned by the server.
		url: the fully-qualified request URL.
		response: the underlying ``requests.Response`` object (may be ``None``
			if the failure occurred before a response was received).
	"""

	def __init__(
		self,
		message: str,
		status_code: Optional[int] = None,
		url: Optional[str] = None,
		response: "Optional[Response]" = None,
	) -> None:
		super().__init__(message)
		self.status_code = status_code
		self.url = url
		self.response = response


class MangaDexAuthError(MangaDexHttpError):
	"""Raised when the API returns 401 or 403."""


class MangaDexRateLimitError(MangaDexHttpError):
	"""Raised when 429 retries are exhausted, or when the server-supplied
	sleep duration exceeds the configured ceiling.

	Attributes:
		retry_after: the number of seconds the server asked us to wait
			before the next retry. ``None`` if unknown.
	"""

	def __init__(
		self,
		message: str,
		status_code: Optional[int] = None,
		url: Optional[str] = None,
		response: "Optional[Response]" = None,
		retry_after: Optional[float] = None,
	) -> None:
		super().__init__(message, status_code=status_code, url=url, response=response)
		self.retry_after = retry_after


class MangaDexNetworkError(MangaDexApiError):
	"""Raised when a request fails due to a network-level error (connection
	reset, timeout, DNS failure, etc.) and retries have been exhausted.

	Attributes:
		url: the fully-qualified request URL.
		original: the underlying exception that caused the failure.
	"""

	def __init__(
		self,
		message: str,
		url: Optional[str] = None,
		original: Optional[BaseException] = None,
	) -> None:
		super().__init__(message)
		self.url = url
		self.original = original
