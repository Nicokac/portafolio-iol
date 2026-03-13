import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.parametros.models import ParametroActivo


@pytest.mark.django_db
def test_parametros_list_view_redirects_anonymous(client):
    response = client.get(reverse("parametros:parametros_list"))
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_parametros_list_view_renders_template_and_context(client):
    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Tecnologia",
        bloque_estrategico="Growth",
        pais_exposicion="USA",
        tipo_patrimonial="Equity",
    )
    user = User.objects.create_user(username="parametros-user", password="testpass123")
    client.force_login(user)

    response = client.get(reverse("parametros:parametros_list"))

    assert response.status_code == 200
    assert "parametros/parametros_list.html" in [t.name for t in response.templates]
    assert "parametros" in response.context
    assert response.context["parametros"].count() == 1
