import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.operaciones_iol.models import OperacionIOL


@pytest.mark.django_db
def test_operaciones_list_view_redirects_anonymous(client):
    response = client.get(reverse("operaciones_iol:operaciones_list"))
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_operaciones_list_view_renders_template_and_context(client):
    OperacionIOL.objects.create(
        numero="OP-1",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="GGAL",
        cantidad=10,
        monto=1000,
        modalidad="PRECIO_LIMITE",
    )
    user = User.objects.create_user(username="operaciones-user", password="testpass123")
    client.force_login(user)

    response = client.get(reverse("operaciones_iol:operaciones_list"))

    assert response.status_code == 200
    assert "operaciones_iol/operaciones_list.html" in [t.name for t in response.templates]
    assert "operaciones" in response.context
    assert response.context["operaciones"].count() == 1
