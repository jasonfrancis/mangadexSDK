"""Unit tests for the ``HttpClient`` retry/backoff policy."""
from __future__ import annotations

import pytest
import responses

from mangadexSdk import httpClient as hc
from mangadexSdk.errors import (
	MangaDexAuthError,
	MangaDexHttpError,
	MangaDexNetworkError,
	MangaDexRateLimitError,
)


BASE = "https://api.mangadex.org"


def _make_client(sleep_recorder, **overrides):
	kwargs = dict(
		base_uri=BASE,
		max_retries=4,
		max_sleep=60.0,
		backoff_base=1.0,
		backoff_cap=30.0,
		jitter=0.0,
		sleep=sleep_recorder,
	)
	kwargs.update(overrides)
	return hc.HttpClient(**kwargs)


@responses.activate
def test_200_returns_response_no_sleeps(sleep_recorder):
	responses.add(responses.GET, f"{BASE}/manga/abc", json={"ok": True}, status=200)
	client = _make_client(sleep_recorder)

	resp = client.get("manga/abc")

	assert resp.status_code == 200
	assert sleep_recorder.calls == []


@responses.activate
def test_honors_retry_after_seconds(sleep_recorder):
	responses.add(
		responses.GET,
		f"{BASE}/manga/abc",
		status=429,
		headers={"Retry-After": "2"},
	)
	responses.add(responses.GET, f"{BASE}/manga/abc", json={"ok": True}, status=200)

	client = _make_client(sleep_recorder)
	resp = client.get("manga/abc")

	assert resp.status_code == 200
	assert sleep_recorder.calls == [pytest.approx(2.0, abs=1e-6)]


@responses.activate
def test_honors_x_ratelimit_retry_after_epoch(sleep_recorder, frozen_time):
	reset_at = frozen_time.now + 3.0
	responses.add(
		responses.GET,
		f"{BASE}/manga/abc",
		status=429,
		headers={"X-RateLimit-Retry-After": str(int(reset_at))},
	)
	responses.add(responses.GET, f"{BASE}/manga/abc", json={"ok": True}, status=200)

	client = _make_client(sleep_recorder)
	resp = client.get("manga/abc")

	assert resp.status_code == 200
	# Epoch-based header -> sleep is approximately reset_at - now.
	assert len(sleep_recorder.calls) == 1
	assert sleep_recorder.calls[0] == pytest.approx(3.0, abs=0.01)


@responses.activate
def test_preemptive_throttle_waits_before_next_call(sleep_recorder, frozen_time):
	reset_at = frozen_time.now + 1.5
	responses.add(
		responses.GET,
		f"{BASE}/manga/abc",
		json={"ok": True},
		status=200,
		headers={
			"X-RateLimit-Limit": "5",
			"X-RateLimit-Remaining": "0",
			"X-RateLimit-Retry-After": repr(reset_at),
		},
	)
	responses.add(responses.GET, f"{BASE}/manga/def", json={"ok": True}, status=200)

	client = _make_client(sleep_recorder)
	client.get("manga/abc")
	# Second call shares the "global" bucket; must preemptively wait.
	client.get("manga/def")

	assert len(sleep_recorder.calls) == 1
	assert sleep_recorder.calls[0] == pytest.approx(1.5, abs=0.01)


@responses.activate
def test_exponential_backoff_on_503(sleep_recorder):
	for _ in range(5):
		responses.add(responses.GET, f"{BASE}/manga/abc", status=503)

	client = _make_client(sleep_recorder, max_retries=4)

	with pytest.raises(MangaDexHttpError) as exc_info:
		client.get("manga/abc")

	assert exc_info.value.status_code == 503
	# 4 retries => 4 sleeps: 1, 2, 4, 8
	assert sleep_recorder.calls == [
		pytest.approx(1.0),
		pytest.approx(2.0),
		pytest.approx(4.0),
		pytest.approx(8.0),
	]


@responses.activate
def test_404_is_not_retried(sleep_recorder):
	responses.add(responses.GET, f"{BASE}/manga/missing", status=404, body="nope")

	client = _make_client(sleep_recorder)

	with pytest.raises(MangaDexHttpError) as exc_info:
		client.get("manga/missing")

	assert exc_info.value.status_code == 404
	assert sleep_recorder.calls == []
	# Only one request was made.
	assert len(responses.calls) == 1


@responses.activate
def test_401_raises_auth_error(sleep_recorder):
	responses.add(responses.GET, f"{BASE}/user/follows/manga/feed", status=401)

	client = _make_client(sleep_recorder)

	with pytest.raises(MangaDexAuthError) as exc_info:
		client.get("user/follows/manga/feed")

	assert exc_info.value.status_code == 401
	assert sleep_recorder.calls == []


@responses.activate
def test_persistent_429_raises_rate_limit_error(sleep_recorder):
	for _ in range(5):
		responses.add(
			responses.GET,
			f"{BASE}/manga/abc",
			status=429,
			headers={"Retry-After": "1"},
		)

	client = _make_client(sleep_recorder, max_retries=4)

	with pytest.raises(MangaDexRateLimitError) as exc_info:
		client.get("manga/abc")

	assert exc_info.value.status_code == 429
	assert exc_info.value.retry_after == pytest.approx(1.0)
	# 4 retries attempted, each sleeping 1s.
	assert sleep_recorder.calls == [pytest.approx(1.0)] * 4


@responses.activate
def test_server_sleep_above_ceiling_raises_immediately(sleep_recorder):
	responses.add(
		responses.GET,
		f"{BASE}/manga/abc",
		status=429,
		headers={"Retry-After": "120"},
	)

	client = _make_client(sleep_recorder, max_sleep=60.0)

	with pytest.raises(MangaDexRateLimitError) as exc_info:
		client.get("manga/abc")

	assert exc_info.value.retry_after == pytest.approx(120.0)
	# No sleeps performed; we bailed out before the first wait.
	assert sleep_recorder.calls == []


@responses.activate
def test_separate_buckets_do_not_cross_throttle(sleep_recorder, frozen_time):
	# at-home/server exhausts its bucket
	responses.add(
		responses.GET,
		f"{BASE}/at-home/server/CID",
		json={"ok": True},
		status=200,
		headers={
			"X-RateLimit-Limit": "40",
			"X-RateLimit-Remaining": "0",
			"X-RateLimit-Retry-After": str(int(frozen_time.now + 10)),
		},
	)
	# A /manga call lives in the "global" bucket and should NOT wait.
	responses.add(responses.GET, f"{BASE}/manga/abc", json={"ok": True}, status=200)

	client = _make_client(sleep_recorder)
	client.get("at-home/server/CID")
	client.get("manga/abc")

	# No preemptive sleep should have happened for the manga call.
	assert sleep_recorder.calls == []


def test_connection_error_then_success(sleep_recorder, monkeypatch):
	"""Transient ConnectionError should trigger exponential backoff and
	then succeed on retry."""
	import requests

	call_count = {"n": 0}

	class FakeResponse:
		status_code = 200
		headers = {}
		text = "{}"

	def fake_request(self, method, url, **kwargs):
		call_count["n"] += 1
		if call_count["n"] <= 2:
			raise requests.ConnectionError("boom")
		return FakeResponse()

	monkeypatch.setattr(hc.requests.Session, "request", fake_request)

	client = _make_client(sleep_recorder, max_retries=4)
	resp = client.get("manga/abc")

	assert resp.status_code == 200
	# Two failed attempts -> two sleeps: 1s, 2s.
	assert sleep_recorder.calls == [pytest.approx(1.0), pytest.approx(2.0)]


def test_persistent_connection_error_raises_network_error(sleep_recorder, monkeypatch):
	import requests

	def fake_request(self, method, url, **kwargs):
		raise requests.ConnectionError("down")

	monkeypatch.setattr(hc.requests.Session, "request", fake_request)

	client = _make_client(sleep_recorder, max_retries=2)
	with pytest.raises(MangaDexNetworkError) as exc_info:
		client.get("manga/abc")

	assert isinstance(exc_info.value.original, requests.ConnectionError)
	# 2 retries => 2 sleeps: 1, 2
	assert sleep_recorder.calls == [pytest.approx(1.0), pytest.approx(2.0)]


@responses.activate
def test_user_agent_is_sent(sleep_recorder):
	responses.add(responses.GET, f"{BASE}/manga/abc", json={"ok": True}, status=200)

	client = _make_client(sleep_recorder, user_agent="custom-ua/1.0")
	client.get("manga/abc")

	assert len(responses.calls) == 1
	assert responses.calls[0].request.headers["User-Agent"] == "custom-ua/1.0"


@responses.activate
def test_post_json_sends_body_and_content_type(sleep_recorder):
	responses.add(responses.POST, f"{BASE}/auth/login", json={"ok": True}, status=200)

	client = _make_client(sleep_recorder)
	client.post_json("auth/login", {"username": "u", "password": "p"})

	req = responses.calls[0].request
	assert req.headers["Content-Type"] == "application/json;charset=utf-8"
	body = req.body
	if isinstance(body, bytes):
		body = body.decode("utf-8")
	assert '"username"' in body


def test_bucket_key_routing():
	assert hc._bucket_key("manga/abc") == "global"
	assert hc._bucket_key("at-home/server/abc") == "at-home/server"
	assert hc._bucket_key("/at-home/server/abc?forcePort443=true") == "at-home/server"
	assert hc._bucket_key("auth/login") == "auth/login"
	assert hc._bucket_key("auth/refresh") == "auth/refresh"
	assert hc._bucket_key("chapter/abc") == "global"
