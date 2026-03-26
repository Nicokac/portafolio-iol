import pytest
from django.test import override_settings
from django.utils import timezone
from unittest.mock import Mock

from apps.core.models import IOLFCICatalogSnapshot
from apps.core.services.iol_fci_admin_taxonomy_service import IOLFCIAdminTaxonomyService


@pytest.mark.django_db
def test_iol_fci_admin_taxonomy_service_uses_local_taxonomy_when_remote_spike_is_disabled():
    captured_at = timezone.now()
    IOLFCICatalogSnapshot.objects.create(
        simbolo="IOLCAMA",
        descripcion="IOL Cash Management",
        source="iol",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        administradora="convexity",
        administradora_key="convexity",
        tipo_fondo="renta_fija_pesos",
        horizonte_inversion="Corto Plazo",
        rescate="t1",
        perfil_inversor="Conservador",
        perfil_inversor_key="conservador",
        moneda="peso_Argentino",
        pais="argentina",
        mercado="bcba",
    )

    client = Mock()
    service = IOLFCIAdminTaxonomyService(client=client)

    payload = service.get_taxonomy_probe("convexity")

    assert payload["feature_enabled"] is False
    assert payload["remote_status"] == "disabled"
    assert payload["local_taxonomy"]["count"] == 1
    assert payload["local_taxonomy"]["items"][0]["identificador_tipo_fondo_fci"] == "renta_fija_pesos"
    client.get_fci_admin_tipo_fondos.assert_not_called()


@pytest.mark.django_db
@override_settings(IOL_FCI_ADMIN_TAXONOMY_SPIKE_ENABLED=True)
def test_iol_fci_admin_taxonomy_service_marks_remote_403_as_forbidden():
    client = Mock()
    client.get_fci_admin_tipo_fondos.return_value = None
    client.last_error = {"status_code": 403, "message": "Forbidden", "error_type": "http_error_after_retry"}

    service = IOLFCIAdminTaxonomyService(client=client)
    payload = service.get_taxonomy_probe("convexity")

    assert payload["feature_enabled"] is True
    assert payload["remote_status"] == "forbidden"
    assert "403" in payload["remote_reason"]
    assert payload["remote_taxonomy"]["count"] == 0


@pytest.mark.django_db
@override_settings(IOL_FCI_ADMIN_TAXONOMY_SPIKE_ENABLED=True)
def test_iol_fci_admin_taxonomy_service_compares_local_and_remote_tipo_fondos():
    captured_at = timezone.now()
    IOLFCICatalogSnapshot.objects.create(
        simbolo="IOLCAMA",
        descripcion="IOL Cash Management",
        source="iol",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        administradora="convexity",
        administradora_key="convexity",
        tipo_fondo="renta_fija_pesos",
        horizonte_inversion="Corto Plazo",
        rescate="t1",
        perfil_inversor="Conservador",
        perfil_inversor_key="conservador",
        moneda="peso_Argentino",
        pais="argentina",
        mercado="bcba",
    )
    IOLFCICatalogSnapshot.objects.create(
        simbolo="IOLPORA",
        descripcion="IOL Portafolio Potenciado",
        source="iol",
        captured_at=captured_at,
        captured_date=captured_at.date(),
        administradora="convexity",
        administradora_key="convexity",
        tipo_fondo="renta_mixta_pesos",
        horizonte_inversion="Mediano Plazo",
        rescate="t1",
        perfil_inversor="Moderado",
        perfil_inversor_key="moderado",
        moneda="peso_Argentino",
        pais="argentina",
        mercado="bcba",
    )

    client = Mock()
    client.get_fci_admin_tipo_fondos.return_value = [
        {"administradora": "convexity", "identificadorTipoFondoFCI": "renta_fija_pesos", "nombreTipoFondoFCI": "Renta Fija Pesos"},
    ]
    client.last_error = {}

    service = IOLFCIAdminTaxonomyService(client=client)
    payload = service.get_taxonomy_probe("convexity")

    assert payload["remote_status"] == "available"
    assert payload["local_taxonomy"]["count"] == 2
    assert payload["remote_taxonomy"]["count"] == 1
    assert payload["comparison"]["matched_count"] == 1
    assert payload["comparison"]["coverage_gap_count"] == 1
