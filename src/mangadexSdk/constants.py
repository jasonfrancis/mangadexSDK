try:
	from importlib.metadata import version as _pkg_version, PackageNotFoundError
except ImportError:  # pragma: no cover - Python < 3.8 not supported anyway
	from importlib_metadata import version as _pkg_version, PackageNotFoundError  # type: ignore


def _resolve_version() -> str:
	try:
		return _pkg_version("mangadexSdk")
	except PackageNotFoundError:
		return "0.0.16"
	except Exception:  # pragma: no cover - defensive
		return "0.0.16"


class Constants:
	SERVICE_ID = "Manga Scraper"
	SETTINGS_FILE = "settings.json"
	BASE_URI = "https://api.mangadex.org"

	# -- HTTP / retry configuration -----------------------------------------
	VERSION = _resolve_version()
	USER_AGENT = f"mangadexSdk/{VERSION} (+https://github.com/anomalyco/mangadexSDK)"

	#: Maximum number of retry attempts per request (does not include the
	#: initial attempt).
	MAX_RETRIES = 5
	#: Hard ceiling on how long the client is willing to sleep in a single
	#: wait. Values above this cause a ``MangaDexRateLimitError`` to be
	#: raised so the caller knows something is wrong.
	MAX_SLEEP_SECONDS = 60.0
	#: Base of the exponential backoff ladder for 5xx / network errors.
	BACKOFF_BASE_SECONDS = 1.0
	#: Cap applied to each exponential-backoff sleep (before jitter).
	BACKOFF_CAP_SECONDS = 30.0
	#: Maximum random jitter added to any sleep to avoid thundering-herd
	#: behavior when many clients hit the same reset epoch.
	JITTER_SECONDS = 0.25
	#: HTTP statuses that trigger a retry.
	RETRY_ON_STATUS = frozenset({429, 502, 503, 504})
