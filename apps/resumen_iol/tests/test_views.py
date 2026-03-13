import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.resumen_iol.models import ResumenCuentaSnapshot
from apps.resumen_iol.views import ResumenListView


@pytest.mark.django_db
def test_resumen_list_view_redirects_anonymous(client):
    response = client.get(reverse("resumen_iol:resumen_list"))
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_resumen_list_view_renders_template_and_context(client):
    ResumenCuentaSnapshot.objects.create(
        fecha_extraccion=timezone.now(),
        numero_cuenta="123",
        tipo_cuenta="CA",
        moneda="ARS",
        disponible=1000,
        comprometido=0,
        saldo=1000,
        titulos_valorizados=0,
        total=1000,
        estado="Activa",
    )
    user = User.objects.create_user(username="resumen-user", password="testpass123")
    client.force_login(user)

    response = client.get(reverse("resumen_iol:resumen_list"))

    assert response.status_code == 200
    assert "resumen_iol/resumen_list.html" in [t.name for t in response.templates]
    assert "resumenes" in response.context
    assert response.context["resumenes"].count() == 1


@pytest.mark.django_db
def test_resumen_list_view_authenticated_renders():
    ResumenCuentaSnapshot.objects.create(
        fecha_extraccion=timezone.now(),
        numero_cuenta="123",
        tipo_cuenta="CA",
        moneda="ARS",
        disponible=1000,
        comprometido=0,
        saldo=1000,
        titulos_valorizados=0,
        total=1000,
        estado="Activa",
    )

    request = RequestFactory().get("/resumen/")
    request.user = User.objects.create_user(username="testuser", password="testpass123")

    view = ResumenListView()
    view.request = request

    assert view.template_name == "resumen_iol/resumen_list.html"
    assert view.context_object_name == "resumenes"
    assert view.get_queryset().count() == 1
