from io import StringIO

import pytest
from django.core.management import call_command

from apps.parametros.models import ConfiguracionDashboard


@pytest.mark.django_db
def test_inicializar_configuraciones_creates_default_records():
    stdout = StringIO()

    call_command("inicializar_configuraciones", stdout=stdout)

    configs = {
        config.clave: config for config in ConfiguracionDashboard.objects.order_by("clave")
    }
    assert set(configs) == {"contribucion_mensual", "moneda_base"}
    assert configs["contribucion_mensual"].valor == "50000"
    assert configs["moneda_base"].valor == "ARS"
    output = stdout.getvalue()
    assert 'Configuración "contribucion_mensual" inicializada' in output
    assert 'Configuración "moneda_base" inicializada' in output


@pytest.mark.django_db
def test_inicializar_configuraciones_is_idempotent():
    call_command("inicializar_configuraciones")
    call_command("inicializar_configuraciones")

    assert ConfiguracionDashboard.objects.filter(clave="contribucion_mensual").count() == 1
    assert ConfiguracionDashboard.objects.filter(clave="moneda_base").count() == 1
