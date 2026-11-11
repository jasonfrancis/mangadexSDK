"""Shared pytest fixtures for the mangadexSdk test suite."""
from __future__ import annotations

from typing import List

import pytest


class SleepRecorder:
	"""Captures calls to ``time.sleep`` so tests can assert on wait times
	without actually blocking."""

	def __init__(self) -> None:
		self.calls: List[float] = []

	def __call__(self, seconds: float) -> None:
		self.calls.append(float(seconds))

	@property
	def total(self) -> float:
		return sum(self.calls)


@pytest.fixture
def sleep_recorder() -> SleepRecorder:
	return SleepRecorder()


@pytest.fixture(autouse=True)
def _no_jitter(monkeypatch):
	"""Make jitter deterministic (always 0) so assertions can be exact."""
	import random
	monkeypatch.setattr(random, "uniform", lambda a, b: 0.0)
	yield


@pytest.fixture
def frozen_time(monkeypatch):
	"""Freeze ``time.time()`` as seen by ``httpClient`` to a known value."""
	from mangadexSdk import httpClient as hc

	state = {"now": 1_700_000_000.0}

	def _time():
		return state["now"]

	monkeypatch.setattr(hc.time, "time", _time)

	def advance(seconds: float) -> None:
		state["now"] += seconds

	# Expose a small controller
	class Controller:
		@property
		def now(self) -> float:
			return state["now"]

		def set(self, value: float) -> None:
			state["now"] = value

		def advance(self, seconds: float) -> None:
			advance(seconds)

	return Controller()
