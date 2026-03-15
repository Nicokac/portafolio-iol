from django.core.cache import cache

from apps.core.services.observability import get_state_summary, record_state


def test_record_state_and_get_state_summary():
    cache.clear()

    record_state("analytics_v2.test.metric", "mvp_proxy", {"observations": 5})
    record_state("analytics_v2.test.metric", "covariance_aware", {"observations": 30})
    record_state("analytics_v2.test.metric", "mvp_proxy", {"observations": 8})

    summary = get_state_summary("analytics_v2.test.metric")

    assert summary["metric_name"] == "analytics_v2.test.metric"
    assert summary["count"] == 3
    assert summary["states"] == {"mvp_proxy": 2, "covariance_aware": 1}
    assert summary["latest_state"] == "mvp_proxy"
    assert summary["latest_extra"] == {"observations": 8}
