import pytest
from django.urls import reverse
from django.utils import timezone

from apps.portafolio_iol.models import ActivoPortafolioSnapshot


@pytest.mark.django_db
def test_portafolio_list_view_renders_template_and_context(client):
    ActivoPortafolioSnapshot.objects.create(
        fecha_extraccion=timezone.now(),
        pais_consulta="Argentina",
        simbolo="AAPL",
        descripcion="Apple",
        cantidad=10,
        comprometido=0,
        disponible_inmediato=10,
        puntos_variacion=0.1,
        variacion_diaria=1.2,
        ultimo_precio=100,
        ppc=90,
        ganancia_porcentaje=11.1,
        ganancia_dinero=100,
        valorizado=1000,
        pais_titulo="USA",
        mercado="NASDAQ",
        tipo="CEDEAR",
        moneda="ARS",
    )

    response = client.get(reverse("portafolio_iol:portafolio_list"))

    assert response.status_code == 200
    assert "portafolio_iol/portafolio_list.html" in [t.name for t in response.templates]
    assert "activos" in response.context
    assert response.context["activos"].count() == 1
