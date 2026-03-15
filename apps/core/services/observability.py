import logging
import time
from contextlib import contextmanager
from typing import Iterator
from collections import Counter

from django.core.cache import cache


logger = logging.getLogger(__name__)
_METRIC_TTL_SECONDS = 60 * 60 * 24
_METRIC_MAX_POINTS = 100


def record_timing(metric_name: str, duration_ms: float) -> None:
    cache_key = f"timing:{metric_name}"
    current = cache.get(cache_key, [])
    updated = (current + [float(duration_ms)])[-_METRIC_MAX_POINTS:]
    cache.set(cache_key, updated, timeout=_METRIC_TTL_SECONDS)
    logger.info(
        "timing metric recorded",
        extra={
            "event": "timing_metric",
            "duration_ms": round(float(duration_ms), 2),
            "extra_data": {"metric_name": metric_name, "points": len(updated)},
        },
    )


def get_timing_summary(metric_name: str) -> dict:
    values = cache.get(f"timing:{metric_name}", [])
    if not values:
        return {"metric_name": metric_name, "count": 0}
    return {
        "metric_name": metric_name,
        "count": len(values),
        "mean_ms": round(sum(values) / len(values), 2),
        "max_ms": round(max(values), 2),
    }


def record_state(metric_name: str, state: str, extra: dict | None = None) -> None:
    cache_key = f"state:{metric_name}"
    current = cache.get(cache_key, [])
    payload = {
        "state": str(state),
        "extra": extra or {},
    }
    updated = (current + [payload])[-_METRIC_MAX_POINTS:]
    cache.set(cache_key, updated, timeout=_METRIC_TTL_SECONDS)
    logger.info(
        "state metric recorded",
        extra={
            "event": "state_metric",
            "extra_data": {"metric_name": metric_name, "state": state, "points": len(updated)},
        },
    )


def get_state_summary(metric_name: str) -> dict:
    values = cache.get(f"state:{metric_name}", [])
    if not values:
        return {"metric_name": metric_name, "count": 0}
    states = [str(item.get("state")) for item in values]
    counts = Counter(states)
    latest = values[-1]
    return {
        "metric_name": metric_name,
        "count": len(values),
        "states": dict(counts),
        "latest_state": latest.get("state"),
        "latest_extra": latest.get("extra", {}),
    }


@contextmanager
def timed(metric_name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        record_timing(metric_name, elapsed_ms)
