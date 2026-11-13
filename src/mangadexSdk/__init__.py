from . import requestTypes
from . import responseTypes
from . import mangaDex
from . import errors
from . import httpClient

RequestTypes = requestTypes.RequestTypes
ResponseTypes = responseTypes
MangadexSdk = mangaDex.MangaDexSdk

# HTTP client + rate-limit types for power users who want to tune behavior.
HttpClient = httpClient.HttpClient
RateBucket = httpClient.RateBucket
get_default_client = mangaDex.get_default_client
set_default_client = mangaDex.set_default_client

# Exception hierarchy.
MangaDexApiError = errors.MangaDexApiError
MangaDexHttpError = errors.MangaDexHttpError
MangaDexAuthError = errors.MangaDexAuthError
MangaDexRateLimitError = errors.MangaDexRateLimitError
MangaDexNetworkError = errors.MangaDexNetworkError
