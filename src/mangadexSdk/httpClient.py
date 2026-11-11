"""HTTP client with MangaDex-aware rate limiting and retry logic.

The policy, in order of preference:

1. **Honor server guidance.** If the server returns ``Retry-After`` or
   ``X-RateLimit-Retry-After`` headers, sleep for exactly that long
   (plus a tiny random jitter to avoid thundering-herd behaviour).
2. **Preemptive throttle.** Track ``X-RateLimit-Remaining`` per bucket;
   if the remaining count is zero, wait until the recorded reset time
   before issuing the next request. This saves a round trip we know
   would come back as a 429.
3. **Exponential backoff** is used only as a fallback for 5xx responses
   that carry no ``Retry-After`` header, and for network-level errors
   such as connection resets and timeouts.
4. **Non-retryable 4xx** responses (anything other than 429) raise
   immediately; they will not get better with retries.
"""
from __future__ import annotations

import email.utils
import json as _json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import requests
from requests import Response

from .constants import Constants
from .errors import (
	MangaDexAuthError,
	MangaDexHttpError,
	MangaDexNetworkError,
	MangaDexRateLimitError,
)

log = logging.getLogger("mangadexSdk.http")


# Path prefixes that have their own tighter per-endpoint rate-limit bucket on
# MangaDex. The prefix is also the bucket key. Everything else shares the
# global ~5 req/s bucket.
_BUCKET_PREFIXES = (
	"auth/login",
	"auth/refresh",
	"at-home/server",
)


def _bucket_key(path: str) -> str:
	# Strip leading slash and query string for matching.
	clean = path.lstrip("/").split("?", 1)[0]
	for prefix in _BUCKET_PREFIXES:
		if clean == prefix or clean.startswith(prefix + "/"):
			return prefix
	return "global"


@dataclass
class RateBucket:
	"""Tracks the rate-limit state for a single bucket of endpoints."""

	limit: Optional[int] = None
	remaining: Optional[int] = None
	reset_at: Optional[float] = None  # epoch seconds

	def update_from_headers(self, headers: "requests.structures.CaseInsensitiveDict") -> None:
		limit = _parse_int(headers.get("X-RateLimit-Limit"))
		remaining = _parse_int(headers.get("X-RateLimit-Remaining"))
		reset_at = _parse_reset_epoch(headers)
		if limit is not None:
			self.limit = limit
		if remaining is not None:
			self.remaining = remaining
		if reset_at is not None:
			self.reset_at = reset_at


def _parse_int(value: Optional[str]) -> Optional[int]:
	if value is None:
		return None
	try:
		return int(value)
	except (TypeError, ValueError):
		return None


def _parse_reset_epoch(headers: "requests.structures.CaseInsensitiveDict") -> Optional[float]:
	"""Return the epoch-seconds reset time, if the server told us one.

	Prefers ``X-RateLimit-Retry-After`` (MangaDex's convention is epoch
	seconds). Falls back to ``X-RateLimit-Reset`` if present.
	"""
	for name in ("X-RateLimit-Retry-After", "X-RateLimit-Reset"):
		raw = headers.get(name)
		if raw is None:
			continue
		as_float = _parse_float(raw)
		if as_float is None:
			continue
		# If the value looks like a small number (< 1e9) treat it as
		# seconds-from-now; otherwise treat it as an absolute epoch. 1e9
		# covers us comfortably until ~2033.
		if as_float < 1_000_000_000:
			return time.time() + as_float
		return as_float
	return None


def _parse_float(value: Any) -> Optional[float]:
	try:
		return float(value)
	except (TypeError, ValueError):
		return None


def _parse_retry_after_header(value: Optional[str]) -> Optional[float]:
	"""Parse the standard ``Retry-After`` header.

	Per RFC 7231 this can be either a non-negative delta in seconds or an
	HTTP-date. Returns the number of seconds to sleep, relative to now.
	"""
	if value is None:
		return None
	value = value.strip()
	if not value:
		return None
	# Integer seconds
	if re.fullmatch(r"\d+(?:\.\d+)?", value):
		try:
			return max(0.0, float(value))
		except ValueError:
			return None
	# HTTP-date
	try:
		dt = email.utils.parsedate_to_datetime(value)
	except (TypeError, ValueError):
		return None
	if dt is None:
		return None
	return max(0.0, dt.timestamp() - time.time())


def _compute_server_sleep(resp: Response) -> Optional[float]:
	"""Return the number of seconds to sleep based on the response's
	rate-limit headers, or ``None`` if the server gave no guidance."""
	candidates = []
	retry_after = _parse_retry_after_header(resp.headers.get("Retry-After"))
	if retry_after is not None:
		candidates.append(retry_after)
	reset_at = _parse_reset_epoch(resp.headers)
	if reset_at is not None:
		candidates.append(max(0.0, reset_at - time.time()))
	if not candidates:
		return None
	# When both are present, trust the larger value: we'd rather wait a
	# touch too long than get bounced again immediately.
	return max(candidates)


class HttpClient:
	"""A ``requests``-backed HTTP client that transparently honors
	MangaDex's rate limit headers and retries on transient failures.
	"""

	def __init__(
		self,
		base_uri: str = Constants.BASE_URI,
		user_agent: Optional[str] = None,
		max_retries: int = Constants.MAX_RETRIES,
		max_sleep: float = Constants.MAX_SLEEP_SECONDS,
		backoff_base: float = Constants.BACKOFF_BASE_SECONDS,
		backoff_cap: float = Constants.BACKOFF_CAP_SECONDS,
		jitter: float = Constants.JITTER_SECONDS,
		retry_on_status: "frozenset[int]" = Constants.RETRY_ON_STATUS,
		session: Optional[requests.Session] = None,
		sleep: Callable[[float], None] = time.sleep,
	) -> None:
		self.base_uri = base_uri.rstrip("/")
		self.user_agent = user_agent or Constants.USER_AGENT
		self.max_retries = max_retries
		self.max_sleep = max_sleep
		self.backoff_base = backoff_base
		self.backoff_cap = backoff_cap
		self.jitter = jitter
		self.retry_on_status = frozenset(retry_on_status)
		self.session = session or requests.Session()
		self._sleep = sleep
		self._buckets: Dict[str, RateBucket] = {}

	# -- Public API ---------------------------------------------------------
	def get(self, path: str, *, headers: Optional[dict] = None) -> Response:
		return self._request("GET", path, headers=headers)

	def post_json(self, path: str, content: Any, *, headers: Optional[dict] = None) -> Response:
		body = _json.dumps(content)
		merged = {"Content-Type": "application/json;charset=utf-8"}
		if headers:
			merged.update(headers)
		return self._request("POST", path, data=body, headers=merged)

	def bucket_for(self, path: str) -> RateBucket:
		"""Return (creating if needed) the ``RateBucket`` that would be used
		for a request against ``path``. Primarily useful for tests and
		diagnostics."""
		key = _bucket_key(path)
		bucket = self._buckets.get(key)
		if bucket is None:
			bucket = RateBucket()
			self._buckets[key] = bucket
		return bucket

	# -- Internals ----------------------------------------------------------
	def _build_url(self, path: str) -> str:
		if path.startswith("http://") or path.startswith("https://"):
			return path
		return f"{self.base_uri}/{path.lstrip('/')}"

	def _request(
		self,
		method: str,
		path: str,
		*,
		data: Any = None,
		headers: Optional[dict] = None,
	) -> Response:
		url = self._build_url(path)
		bucket = self.bucket_for(path)

		merged_headers = {"User-Agent": self.user_agent}
		if headers:
			merged_headers.update(headers)

		last_error: Optional[BaseException] = None

		# Total number of send attempts is max_retries + 1 (initial try).
		for attempt in range(self.max_retries + 1):
			# (1) Preemptive throttle: if the bucket is exhausted and we
			# know when it resets, wait it out before firing.
			self._preemptive_wait(bucket, url)

			try:
				resp = self.session.request(
					method,
					url,
					data=data,
					headers=merged_headers,
				)
			except (requests.ConnectionError, requests.Timeout) as exc:
				last_error = exc
				if attempt >= self.max_retries:
					raise MangaDexNetworkError(
						f"Network error on {method} {url} after {attempt + 1} attempts: {exc}",
						url=url,
						original=exc,
					) from exc
				sleep_for = self._exp_backoff(attempt)
				log.warning(
					"Network error on %s %s (attempt %d/%d): %s; sleeping %.2fs",
					method, url, attempt + 1, self.max_retries + 1, exc, sleep_for,
				)
				self._sleep(sleep_for)
				continue

			# Update bucket from any headers the server sent us.
			bucket.update_from_headers(resp.headers)

			status = resp.status_code

			# (2) Success.
			if 200 <= status < 300:
				return resp

			# (3) Retryable statuses.
			if status in self.retry_on_status:
				if attempt >= self.max_retries:
					self._raise_for_exhausted(method, url, resp)
				sleep_for = self._sleep_for_retry(resp, attempt)
				if sleep_for > self.max_sleep:
					raise MangaDexRateLimitError(
						(
							f"Server asked us to wait {sleep_for:.1f}s on "
							f"{method} {url}, which exceeds the configured "
							f"max_sleep={self.max_sleep}s."
						),
						status_code=status,
						url=url,
						response=resp,
						retry_after=sleep_for,
					)
				log.info(
					"Got %d on %s %s (attempt %d/%d); sleeping %.2fs before retry",
					status, method, url, attempt + 1, self.max_retries + 1, sleep_for,
				)
				self._sleep(sleep_for)
				continue

			# (4) Non-retryable: fail fast.
			self._raise_for_status(method, url, resp)

		# Defensive: the loop should always return or raise.
		if last_error is not None:  # pragma: no cover - unreachable
			raise MangaDexNetworkError(
				f"Request failed: {last_error}", url=url, original=last_error
			)
		raise MangaDexApiError(f"Request to {url} exhausted retries")  # type: ignore[name-defined]  # pragma: no cover

	# -- helpers ------------------------------------------------------------
	def _preemptive_wait(self, bucket: RateBucket, url: str) -> None:
		if bucket.remaining is None or bucket.reset_at is None:
			return
		if bucket.remaining > 0:
			return
		wait = bucket.reset_at - time.time()
		if wait <= 0:
			# Reset time has already passed; optimistically assume the
			# bucket has refilled.
			bucket.remaining = bucket.limit
			return
		wait = min(wait + self._random_jitter(), self.max_sleep)
		if wait >= self.max_sleep:
			raise MangaDexRateLimitError(
				(
					f"Rate-limit bucket exhausted; need to wait "
					f"{bucket.reset_at - time.time():.1f}s before the next "
					f"request to {url}, which exceeds max_sleep={self.max_sleep}s."
				),
				url=url,
				retry_after=bucket.reset_at - time.time(),
			)
		log.info(
			"Preemptively sleeping %.2fs for rate-limit bucket reset before %s",
			wait, url,
		)
		self._sleep(wait)
		# After waiting, treat the bucket as refilled.
		bucket.remaining = bucket.limit

	def _sleep_for_retry(self, resp: Response, attempt: int) -> float:
		server_hint = _compute_server_sleep(resp)
		if server_hint is not None:
			return max(0.0, server_hint) + self._random_jitter()
		# No server guidance; use capped exponential backoff.
		return self._exp_backoff(attempt)

	def _exp_backoff(self, attempt: int) -> float:
		raw = self.backoff_base * (2 ** attempt)
		capped = min(raw, self.backoff_cap)
		return capped + self._random_jitter()

	def _random_jitter(self) -> float:
		if self.jitter <= 0:
			return 0.0
		return random.uniform(0.0, self.jitter)

	def _raise_for_exhausted(self, method: str, url: str, resp: Response) -> None:
		status = resp.status_code
		if status == 429:
			raise MangaDexRateLimitError(
				(
					f"Rate limited on {method} {url}: {status} after exhausting "
					f"{self.max_retries} retries."
				),
				status_code=status,
				url=url,
				response=resp,
				retry_after=_compute_server_sleep(resp),
			)
		raise MangaDexHttpError(
			(
				f"{method} {url} failed after exhausting {self.max_retries} "
				f"retries. Last status: {status} - {_safe_body(resp)}"
			),
			status_code=status,
			url=url,
			response=resp,
		)

	def _raise_for_status(self, method: str, url: str, resp: Response) -> None:
		status = resp.status_code
		body = _safe_body(resp)
		if status in (401, 403):
			raise MangaDexAuthError(
				f"{method} {url} failed authentication: {status} - {body}",
				status_code=status,
				url=url,
				response=resp,
			)
		raise MangaDexHttpError(
			f"{method} {url} failed. Status code {status} - {body}",
			status_code=status,
			url=url,
			response=resp,
		)


def _safe_body(resp: Response, limit: int = 500) -> str:
	try:
		text = resp.text or ""
	except Exception:  # pragma: no cover - defensive
		return "<unreadable response body>"
	if len(text) > limit:
		return text[:limit] + "...<truncated>"
	return text
