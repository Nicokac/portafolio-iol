from types import SimpleNamespace

import pandas as pd
import pytest
from django.utils import timezone

from apps.portafolio_iol.models import ActivoPortafolioSnapshot

from apps.core.services.iol_market_snapshot_support import (
    get_current_portfolio_market_snapshot_rows,
    summarize_recent_market_history_rows,
)


@pytest.mark.django_db
def test_get_current_portfolio_market_snapshot_rows_marks_missing_snapshot():
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=timezone.make_aware(pd.Timestamp("2026-03-20 10:00:00").to_pydatetime()),
        pais_consulta="argentina",
        simbolo="GGAL",
        descripcion="Grupo Galicia",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0,
        variacion_diaria=0,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=0,
        ganancia_dinero=0,
        valorizado=1000,
        pais_titulo="Argentina",
        mercado="BCBA",
        tipo="ACCIONES",
        moneda="ARS",
    )
    service = SimpleNamespace(
        classify_position_for_history=lambda row: {"supported": True},
        _resolve_market_snapshot=lambda **kwargs: None,
        _build_snapshot_source_label=lambda source_key: source_key or "",
    )

    rows = get_current_portfolio_market_snapshot_rows(service, limit=5)

    assert rows[0]["simbolo"] == "GGAL"
    assert rows[0]["snapshot_status"] == "missing"


def test_summarize_recent_market_history_rows_prioritizes_weak_status():
    summary = summarize_recent_market_history_rows(
        [
            {"quality_status": "strong"},
            {"quality_status": "watch"},
            {"quality_status": "weak"},
        ]
    )

    assert summary["overall_status"] == "weak"
    assert summary["weak_count"] == 1
