from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.core.models import IOLFCICatalogSnapshot
from apps.core.services.iol_fci_catalog_service import IOLFCICatalogService


@pytest.mark.django_db
class TestIOLFCICatalogService:
    def test_sync_catalog_persists_rows(self):
        client = Mock()
        client.get_fci_list.return_value = [
            {
                "simbolo": "IOLPORA",
                "descripcion": "IOL Portafolio Potenciado",
                "tipoAdministradoraTituloFCI": "convexity",
                "tipoFondo": "renta_mixta_pesos",
                "horizonteInversion": "Mediano Plazo",
                "rescate": "t1",
                "perfilInversor": "Moderado",
                "moneda": "peso_Argentino",
                "pais": "argentina",
                "mercado": "bcba",
                "ultimoOperado": 1.360395,
                "variacion": 0.43,
                "variacionMensual": 1.85,
                "variacionAnual": 2.22,
                "montoMinimo": 0,
                "fechaCorte": "1900-01-01T15:00:00",
            }
        ]
        service = IOLFCICatalogService(client=client)
        captured_at = timezone.make_aware(datetime(2026, 3, 26, 18, 0, 0))

        result = service.sync_catalog(captured_at=captured_at)

        assert result["success"] is True
        assert result["created"] == 1
        snapshot = IOLFCICatalogSnapshot.objects.get(simbolo="IOLPORA")
        assert snapshot.tipo_fondo == "renta_mixta_pesos"
        assert snapshot.rescate == "t1"
        assert snapshot.perfil_inversor_key == "moderado"
        assert snapshot.administradora_key == "convexity"
        assert snapshot.captured_date.isoformat() == "2026-03-26"

    def test_list_latest_catalog_filters_latest_day_only(self):
        older_day = timezone.make_aware(datetime(2026, 3, 25, 18, 0, 0))
        latest_day = timezone.make_aware(datetime(2026, 3, 26, 18, 0, 0))
        IOLFCICatalogSnapshot.objects.create(
            simbolo="OLDROW",
            descripcion="Old",
            captured_at=older_day,
            captured_date=older_day.date(),
            administradora="convexity",
            administradora_key="convexity",
            tipo_fondo="renta_fija_pesos",
            rescate="t1",
            perfil_inversor="Moderado",
            perfil_inversor_key="moderado",
            moneda="peso_Argentino",
            pais="argentina",
            mercado="bcba",
        )
        IOLFCICatalogSnapshot.objects.create(
            simbolo="IOLCAMA",
            descripcion="IOL Cash Management",
            captured_at=latest_day,
            captured_date=latest_day.date(),
            administradora="convexity",
            administradora_key="convexity",
            tipo_fondo="renta_fija_pesos",
            rescate="t1",
            perfil_inversor="Conservador",
            perfil_inversor_key="conservador",
            moneda="peso_Argentino",
            pais="argentina",
            mercado="bcba",
        )
        IOLFCICatalogSnapshot.objects.create(
            simbolo="IOLDOLD",
            descripcion="IOL Dolar Ahorro Plus",
            captured_at=latest_day,
            captured_date=latest_day.date(),
            administradora="convexity",
            administradora_key="convexity",
            tipo_fondo="renta_fija_dolares",
            rescate="t1",
            perfil_inversor="Conservador",
            perfil_inversor_key="conservador",
            moneda="dolar_Estadounidense",
            pais="argentina",
            mercado="bcba",
        )

        payload = IOLFCICatalogService().list_latest_catalog(
            tipo_fondo="renta_fija_pesos",
            moneda="peso_Argentino",
            perfil_inversor="Conservador",
        )

        assert payload["captured_date"] == "2026-03-26"
        assert payload["count"] == 1
        assert payload["items"][0]["simbolo"] == "IOLCAMA"

    def test_get_fci_detail_uses_latest_snapshot_and_builds_strategy_profile(self):
        captured_at = timezone.make_aware(datetime(2026, 3, 26, 18, 0, 0))
        IOLFCICatalogSnapshot.objects.create(
            simbolo="IOLCAMA",
            descripcion="IOL Cash Management",
            captured_at=captured_at,
            captured_date=captured_at.date(),
            administradora="convexity",
            administradora_key="convexity",
            tipo_fondo="renta_fija_pesos",
            horizonte_inversion="Corto plazo",
            rescate="t1",
            perfil_inversor="Conservador",
            perfil_inversor_key="conservador",
            moneda="peso_Argentino",
            pais="argentina",
            mercado="bcba",
            variacion_mensual=Decimal("2.49"),
            variacion_anual=Decimal("8.24"),
            monto_minimo=Decimal("0"),
            metadata={},
        )

        payload = IOLFCICatalogService().get_fci_detail("IOLCAMA", fallback_live=False)

        assert payload["simbolo"] == "IOLCAMA"
        assert payload["strategy_profile"]["classification"] == "cash_management"
        assert payload["strategy_profile"]["liquidity_label"] == "Liquidez 24h"
        assert payload["metadata"]["detail_source"] == "latest_catalog_snapshot"

    def test_get_profiles_for_symbols_returns_only_latest_catalog_matches(self):
        older_day = timezone.make_aware(datetime(2026, 3, 25, 18, 0, 0))
        latest_day = timezone.make_aware(datetime(2026, 3, 26, 18, 0, 0))
        IOLFCICatalogSnapshot.objects.create(
            simbolo="SCHRINS",
            descripcion="Fondo retorno",
            captured_at=older_day,
            captured_date=older_day.date(),
            administradora="convexity",
            administradora_key="convexity",
            tipo_fondo="renta_variable_pesos",
            horizonte_inversion="Largo Plazo",
            rescate="t1",
            perfil_inversor="Agresivo",
            perfil_inversor_key="agresivo",
            moneda="peso_Argentino",
            pais="argentina",
            mercado="bcba",
        )
        IOLFCICatalogSnapshot.objects.create(
            simbolo="SCHRINS",
            descripcion="Fondo retorno",
            captured_at=latest_day,
            captured_date=latest_day.date(),
            administradora="convexity",
            administradora_key="convexity",
            tipo_fondo="renta_variable_pesos",
            horizonte_inversion="Largo Plazo",
            rescate="t2",
            perfil_inversor="Agresivo",
            perfil_inversor_key="agresivo",
            moneda="peso_Argentino",
            pais="argentina",
            mercado="bcba",
            metadata={},
        )

        payload = IOLFCICatalogService().get_profiles_for_symbols(["SCHRINS", "MISSING"])

        assert list(payload.keys()) == ["SCHRINS"]
        assert payload["SCHRINS"]["strategy_profile"]["classification"] == "return_seeking"
        assert payload["SCHRINS"]["rescate"] == "t2"
