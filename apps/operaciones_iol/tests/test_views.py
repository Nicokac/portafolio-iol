import pytest
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SensitiveActionAudit
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
        estado_actual="terminada",
        mercado="BCBA",
        simbolo="GGAL",
        cantidad=10,
        monto=1000,
        modalidad="PRECIO_LIMITE",
        moneda="peso_Argentino",
        aranceles_ars=25.50,
        operaciones_detalle=[{"fecha": "2026-03-18T14:05:57", "cantidad": 10, "precio": 100}],
    )
    user = User.objects.create_user(username="operaciones-user", password="testpass123")
    client.force_login(user)

    response = client.get(reverse("operaciones_iol:operaciones_list"))

    assert response.status_code == 200
    assert "operaciones_iol/operaciones_list.html" in [t.name for t in response.templates]
    assert "operaciones" in response.context
    assert response.context["operaciones"].count() == 1
    assert "operation_rows" in response.context
    assert "operations_summary" in response.context
    assert response.context["operations_summary"]["enriched_count"] == 1
    assert str(response.context["operations_summary"]["enriched_pct"]) == "100.00"
    assert reverse("operaciones_iol:operacion_detail", args=["OP-1"]) in response.content.decode()
    body = response.content.decode()
    assert "Hoja de operaciones" in body
    assert "Filtros analiticos" in body
    assert "Pais IOL" in body
    assert "Detalle IOL" in body
    assert "Ejecucion" in body
    assert "Enriquecido" in body
    assert "Calidad de ejecucion visible" in body
    assert "1 de 1 operaciones con detalle IOL utilizable." in body
    assert "Compra: 1" in body


@pytest.mark.django_db
def test_operaciones_list_view_applies_filters_from_query_params(client):
    OperacionIOL.objects.create(
        numero="167788363",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        estado_actual="terminada",
        mercado="BCBA",
        simbolo="MELI",
        modalidad="precio_Mercado",
    )
    OperacionIOL.objects.create(
        numero="167700000",
        fecha_orden=timezone.now() - timezone.timedelta(days=10),
        tipo="Compra",
        estado="Pendiente",
        mercado="BCBA",
        simbolo="GGAL",
        modalidad="precio_Mercado",
    )
    user = User.objects.create_user(username="operaciones-filter-user", password="testpass123")
    client.force_login(user)

    response = client.get(
        reverse("operaciones_iol:operaciones_list"),
        {
            "numero": "167788",
            "estado": "terminada",
            "fecha_desde": (timezone.now() - timezone.timedelta(days=2)).date().isoformat(),
            "fecha_hasta": timezone.now().date().isoformat(),
            "pais": "estados_Unidos",
        },
    )

    assert response.status_code == 200
    assert response.context["operaciones"].count() == 1
    assert response.context["operaciones"].first().numero == "167788363"
    assert response.context["operation_filters"]["active_count"] == 5
    body = response.content.decode()
    assert "5 filtros activos" in body
    assert "167788363" in body
    assert "167700000" not in body


@pytest.mark.django_db
def test_sync_operaciones_filtered_requires_staff(client):
    user = User.objects.create_user(username="operaciones-non-staff", password="testpass123")
    client.force_login(user)
    response = client.post(reverse("operaciones_iol:sync_operaciones_filtered"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_sync_operaciones_filtered_calls_service_and_audits(client, monkeypatch):
    staff = User.objects.create_user(username="staff-operaciones", password="testpass123", is_staff=True)
    client.force_login(staff)

    captured = {}

    class DummyService:
        def sync_operaciones(self, params=None):
            captured["params"] = params
            return True

    monkeypatch.setattr("apps.operaciones_iol.views.IOLSyncService", lambda: DummyService())

    response = client.post(
        reverse("operaciones_iol:sync_operaciones_filtered"),
        {
            "numero": "167788363",
            "estado": "terminada",
            "fecha_desde": "2026-03-01",
            "fecha_hasta": "2026-03-21",
            "pais": "estados_Unidos",
        },
        follow=True,
    )

    assert response.status_code == 200
    assert captured["params"] == {
        "numero": "167788363",
        "estado": "terminada",
        "fecha_desde": "2026-03-01",
        "fecha_hasta": "2026-03-21",
        "pais": "estados_Unidos",
    }
    messages = list(get_messages(response.wsgi_request))
    assert any("Operaciones sincronizadas desde IOL" in str(message) for message in messages)
    audit = SensitiveActionAudit.objects.get(action="sync_operaciones_filtered")
    assert audit.status == "success"
    assert audit.user.username == "staff-operaciones"
    assert audit.details["filters"]["pais"] == "estados_Unidos"


@pytest.mark.django_db
def test_operacion_detail_view_renders_existing_detail(client):
    operacion = OperacionIOL.objects.create(
        numero="167788363",
        fecha_orden=timezone.now(),
        fecha_alta=timezone.now(),
        fecha_operada=timezone.now(),
        validez=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        estado_actual="terminada",
        mercado="BCBA",
        simbolo="MCD",
        moneda="peso_Argentino",
        cantidad=4,
        monto=98300,
        modalidad="precio_Mercado",
        precio=19950,
        monto_operacion=78720,
        aranceles_ars=523.89,
        plazo="a24horas",
        estados_detalle=[{"detalle": "Terminada", "fecha": "2026-03-18T14:05:58.507"}],
        aranceles_detalle=[{"tipo": "Comision", "neto": 393.6, "iva": 82.66, "moneda": "PESO_ARGENTINO"}],
        operaciones_detalle=[{"fecha": "2026-03-18T14:05:57", "cantidad": 4, "precio": 19680}],
    )
    user = User.objects.create_user(username="operacion-detail-user", password="testpass123")
    client.force_login(user)

    response = client.get(reverse("operaciones_iol:operacion_detail", args=[operacion.numero]))

    assert response.status_code == 200
    body = response.content.decode()
    assert "Operacion 167788363" in body
    assert "Detalle operativo enriquecido" in body
    assert "Timeline de estados" in body
    assert "Fills" in body
    assert "Aranceles" in body
    assert "Re-sincronizar detalle IOL" in body
    assert "MCD" in body


@pytest.mark.django_db
def test_operacion_detail_view_syncs_missing_detail_on_demand(client, monkeypatch):
    operacion = OperacionIOL.objects.create(
        numero="167788363",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MCD",
        modalidad="precio_Mercado",
    )
    user = User.objects.create_user(username="operacion-sync-user", password="testpass123")
    client.force_login(user)

    class DummyService:
        def sync_operacion_detalle(self, numero):
            updated = OperacionIOL.objects.get(numero=str(numero))
            updated.moneda = "peso_Argentino"
            updated.estado_actual = "terminada"
            updated.estados_detalle = [{"detalle": "Terminada", "fecha": "2026-03-18T14:05:58.507"}]
            updated.operaciones_detalle = [{"fecha": "2026-03-18T14:05:57", "cantidad": 4, "precio": 19680}]
            updated.aranceles_detalle = [{"tipo": "Comision", "neto": 393.6, "iva": 82.66, "moneda": "PESO_ARGENTINO"}]
            updated.save()
            return True

    monkeypatch.setattr("apps.operaciones_iol.views.IOLSyncService", lambda: DummyService())

    response = client.get(reverse("operaciones_iol:operacion_detail", args=[operacion.numero]))

    assert response.status_code == 200
    operacion.refresh_from_db()
    assert operacion.moneda == "peso_Argentino"
    messages = list(get_messages(response.wsgi_request))
    assert any("Se actualiz" in str(message) and "detalle de la operaci" in str(message) for message in messages)


@pytest.mark.django_db
def test_operacion_detail_view_post_resync_updates_detail_and_audits(client, monkeypatch):
    operacion = OperacionIOL.objects.create(
        numero="167788363",
        fecha_orden=timezone.now(),
        tipo="Compra",
        estado="Terminada",
        mercado="BCBA",
        simbolo="MCD",
        modalidad="precio_Mercado",
    )
    user = User.objects.create_user(username="operacion-post-sync-user", password="testpass123")
    client.force_login(user)

    class DummyService:
        def sync_operacion_detalle(self, numero):
            updated = OperacionIOL.objects.get(numero=str(numero))
            updated.moneda = "peso_Argentino"
            updated.estado_actual = "terminada"
            updated.estados_detalle = [{"detalle": "En Proceso", "fecha": "2026-03-18T14:05:58.4"}]
            updated.save()
            return True

    monkeypatch.setattr("apps.operaciones_iol.views.IOLSyncService", lambda: DummyService())

    response = client.post(reverse("operaciones_iol:operacion_detail", args=[operacion.numero]), follow=True)

    assert response.status_code == 200
    operacion.refresh_from_db()
    assert operacion.moneda == "peso_Argentino"
    messages = list(get_messages(response.wsgi_request))
    assert any("re-sincronizado desde IOL" in str(message) for message in messages)

    audit = SensitiveActionAudit.objects.get(action="operacion_detail_resync")
    assert audit.status == "success"
    assert audit.details["numero"] == operacion.numero
