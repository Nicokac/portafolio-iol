import pytest
from django.urls import reverse

from apps.parametros.models import ParametroActivo


@pytest.mark.django_db
def test_parametros_list_view_renders_template_and_context(client):
    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )

    response = client.get(reverse("parametros:parametros_list"))

    assert response.status_code == 200
    assert "parametros/parametros_list.html" in [t.name for t in response.templates]
    assert "parametros" in response.context
    assert response.context["parametros"].count() == 1
