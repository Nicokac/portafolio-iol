from io import StringIO

import pytest
from django.core.management import call_command

from apps.parametros.models import ConfiguracionDashboard, ParametroActivo


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


@pytest.mark.django_db
def test_cargar_metadata_creates_bootstrap_asset_metadata():
    stdout = StringIO()

    call_command("cargar_metadata", stdout=stdout)

    assert ParametroActivo.objects.filter(simbolo="AAPL").exists()
    assert ParametroActivo.objects.filter(simbolo="CAUCIÓN COLOCADORA").exists()

    aapl = ParametroActivo.objects.get(simbolo="AAPL")
    caucion = ParametroActivo.objects.get(simbolo="CAUCIÓN COLOCADORA")

    assert aapl.sector == "Tecnología"
    assert aapl.bloque_estrategico == "Growth"
    assert aapl.tipo_patrimonial == "Equity"
    assert caucion.bloque_estrategico == "Liquidez"
    assert caucion.tipo_patrimonial == "Cash"
    assert "Carga completada" in stdout.getvalue()


@pytest.mark.django_db
def test_cargar_metadata_is_idempotent_and_updates_existing_records():
    ParametroActivo.objects.create(
        simbolo="AAPL",
        sector="Viejo",
        bloque_estrategico="Viejo",
        pais_exposicion="Viejo",
        tipo_patrimonial="Viejo",
        observaciones="Viejo",
    )

    call_command("cargar_metadata")
    call_command("cargar_metadata")

    assert ParametroActivo.objects.filter(simbolo="AAPL").count() == 1
    aapl = ParametroActivo.objects.get(simbolo="AAPL")
    assert aapl.sector == "Tecnología"
    assert aapl.bloque_estrategico == "Growth"
    assert aapl.pais_exposicion == "USA"
    assert aapl.tipo_patrimonial == "Equity"


@pytest.mark.django_db
def test_cargar_metadata_dry_run_does_not_persist_changes():
    stdout = StringIO()

    call_command("cargar_metadata", dry_run=True, stdout=stdout)

    assert ParametroActivo.objects.count() == 0
    assert "Dry run" in stdout.getvalue()
