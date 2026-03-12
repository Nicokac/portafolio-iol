import logging
import time
from contextlib import contextmanager
from typing import Iterator

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


@contextmanager
def timed(metric_name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        record_timing(metric_name, elapsed_ms)
