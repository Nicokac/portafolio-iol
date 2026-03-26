from unittest.mock import Mock

import pytest

from apps.core.services.iol_orleans_spike_service import IOLOrleansSpikeService


@pytest.mark.django_db
def test_iol_orleans_spike_service_returns_disabled_probe_when_flag_is_off(settings):
    settings.IOL_ORLEANS_SPIKE_ENABLED = False

    service = IOLOrleansSpikeService(client=Mock(), coverage_service=Mock())

    payload = service.get_probe(instrumento='Bonos', pais='argentina')

    assert payload['status'] == 'disabled'
    assert payload['feature_enabled'] is False
    assert payload['baseline']['count'] == 0
    assert payload['comparisons'] == {}


@pytest.mark.django_db
def test_iol_orleans_spike_service_marks_remote_401_as_unauthorized(settings):
    settings.IOL_ORLEANS_SPIKE_ENABLED = True
    client = Mock()
    client.get_bulk_quotes.return_value = None
    client.get_orleans_bulk_quotes.return_value = None
    client.get_orleans_operables.return_value = None
    client.get_orleans_panel_bulk_quotes.return_value = None
    client.get_orleans_panel_operables.return_value = None
    client.last_error = {'status_code': 401, 'message': 'Authorization has been denied for this request.'}

    service = IOLOrleansSpikeService(client=client, coverage_service=Mock())

    payload = service.get_probe(instrumento='Bonos', pais='argentina')

    assert payload['status'] == 'available'
    assert payload['baseline']['status'] == 'unauthorized'
    assert payload['orleans']['status'] == 'unauthorized'
    assert payload['orleans_panel']['status'] == 'unauthorized'


@pytest.mark.django_db
def test_iol_orleans_spike_service_compares_symbol_overlap(settings):
    settings.IOL_ORLEANS_SPIKE_ENABLED = True
    client = Mock()
    client.get_bulk_quotes.return_value = {'titulos': [{'simbolo': 'AL30'}, {'simbolo': 'GD30'}]}
    client.get_orleans_bulk_quotes.return_value = {'titulos': [{'simbolo': 'AL30'}, {'simbolo': 'TX26'}]}
    client.get_orleans_operables.return_value = {'titulos': [{'simbolo': 'AL30'}]}
    client.get_orleans_panel_bulk_quotes.return_value = {'titulos': [{'simbolo': 'AL30'}, {'simbolo': 'GD30'}]}
    client.get_orleans_panel_operables.return_value = {'titulos': [{'simbolo': 'AL30'}]}
    client.last_error = {}

    coverage_service = Mock()
    coverage_service._build_snapshot_row.side_effect = [
        {
            'total_titles': 2,
            'coverage_pct': 100.0,
            'order_book_coverage_pct': 50.0,
            'activity_pct': 50.0,
            'freshness_status': 'fresh',
            'latest_quote_age_minutes': 3,
            'stale_titles': 0,
            'metadata': {},
        },
        {
            'total_titles': 2,
            'coverage_pct': 100.0,
            'order_book_coverage_pct': 50.0,
            'activity_pct': 50.0,
            'freshness_status': 'fresh',
            'latest_quote_age_minutes': 4,
            'stale_titles': 0,
            'metadata': {},
        },
        {
            'total_titles': 1,
            'coverage_pct': 100.0,
            'order_book_coverage_pct': 100.0,
            'activity_pct': 100.0,
            'freshness_status': 'fresh',
            'latest_quote_age_minutes': 2,
            'stale_titles': 0,
            'metadata': {},
        },
        {
            'total_titles': 2,
            'coverage_pct': 100.0,
            'order_book_coverage_pct': 100.0,
            'activity_pct': 50.0,
            'freshness_status': 'fresh',
            'latest_quote_age_minutes': 5,
            'stale_titles': 0,
            'metadata': {},
        },
        {
            'total_titles': 1,
            'coverage_pct': 100.0,
            'order_book_coverage_pct': 100.0,
            'activity_pct': 100.0,
            'freshness_status': 'fresh',
            'latest_quote_age_minutes': 2,
            'stale_titles': 0,
            'metadata': {},
        },
    ]
    coverage_service._as_str.side_effect = lambda value: str(value or '').strip()

    service = IOLOrleansSpikeService(client=client, coverage_service=coverage_service)

    payload = service.get_probe(instrumento='Bonos', pais='argentina')

    assert payload['baseline']['count'] == 2
    assert payload['orleans']['count'] == 2
    assert payload['comparisons']['baseline_vs_orleans']['overlap_count'] == 1
    assert payload['comparisons']['orleans_todos_vs_operables']['right_count'] == 1
