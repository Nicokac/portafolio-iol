from django.test import TestCase
from decimal import Decimal
from django.utils import timezone

from apps.dashboard.selectors import (
    get_analytics_mensual,
    get_concentracion_pais,
    get_concentracion_sector,
    get_concentracion_tipo_patrimonial,
    get_dashboard_kpis,
    get_distribucion_moneda,
    get_distribucion_moneda_operativa,
    get_distribucion_pais,
    get_distribucion_sector,
    get_distribucion_tipo_patrimonial,
    get_evolucion_historica,
    get_riesgo_portafolio,
    get_senales_rebalanceo,
)
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


class TestDashboardSelectors(TestCase):
    def test_get_dashboard_kpis_no_data(self):
        kpis = get_dashboard_kpis()
        assert kpis == {
            'total_iol': 0,
            'titulos_valorizados': 0,
            'cash_ars': 0,
            'cash_usd': 0,
            'liquidez_operativa': 0,
            'fci_cash_management': 0,
            'portafolio_invertido': 0,
            'capital_invertido_real': 0,
            'rendimiento_total_porcentaje': 0,
            'rendimiento_total_dinero': 0,
            'top_5_concentracion': 0,
            'top_10_concentracion': 0,
            'pct_fci_cash_management': 0,
            'pct_portafolio_invertido': 0,
        }

    def test_get_dashboard_kpis_with_data(self):
        # Crear datos de prueba
        fecha = timezone.now()
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=fecha,
            numero_cuenta='123',
            tipo_cuenta='CA',
            moneda='ARS',
            disponible=1000.00,
            comprometido=0.00,
            saldo=1000.00,
            titulos_valorizados=0.00,
            total=1000.00,
            estado='activa',
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            pais_consulta='argentina',
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=10,
            comprometido=0,
            disponible_inmediato=10,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=100.00,
            ppc=90.00,
            ganancia_porcentaje=11.11,
            ganancia_dinero=111.10,
            valorizado=1000.00,
            pais_titulo='Estados Unidos',
            mercado='NASDAQ',
            tipo='ACCIONES',
            moneda='USD',
        )

        kpis = get_dashboard_kpis()
        assert kpis['cash_ars'] == Decimal('1000.00')
        assert kpis['cash_usd'] == Decimal('0.00')
        assert kpis['titulos_valorizados'] == Decimal('1000.00')  # AAPL es ACCIONES
        assert kpis['total_iol'] == Decimal('2000.00')  # 1000 activos + 1000 cash ARS
        assert kpis['liquidez_operativa'] == Decimal('1000.00')  # solo cash ARS
        assert kpis['capital_invertido_real'] == Decimal('1000.00')  # total_iol - liquidez_operativa - fci_cash
        assert kpis['rendimiento_total_dinero'] == Decimal('111.10')  # ganancia_dinero del activo
        assert abs(kpis['rendimiento_total_porcentaje'] - Decimal('11.11')) < Decimal('0.01')

    def test_get_dashboard_kpis_with_percentages(self):
        """Test que los KPIs incluyen los porcentajes de los bloques patrimoniales."""
        fecha = timezone.now()
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=fecha,
            numero_cuenta='123',
            tipo_cuenta='CA',
            moneda='ARS',
            disponible=1000.00,
            comprometido=0.00,
            saldo=1000.00,
            titulos_valorizados=0.00,
            total=1000.00,
            estado='activa',
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            pais_consulta='argentina',
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=10,
            comprometido=0,
            disponible_inmediato=10,
            puntos_variacion=0,
            variacion_diaria=0,
            ultimo_precio=100.00,
            ppc=90.00,
            ganancia_porcentaje=11.11,
            ganancia_dinero=111.10,
            valorizado=1000.00,
            pais_titulo='Estados Unidos',
            mercado='NASDAQ',
            tipo='ACCIONES',
            moneda='USD',
        )

        kpis = get_dashboard_kpis()

        # Verificar que se incluyen los porcentajes
        assert 'pct_fci_cash_management' in kpis
        assert 'pct_portafolio_invertido' in kpis

        # Total IOL = 2000, liquidez operativa = 1000, pct_liquidez ya estaba en riesgo_portafolio
        # pct_fci_cash_management debería ser 0% (no hay FCI cash)
        # pct_portafolio_invertido debería ser 50% (1000/2000)
        assert kpis['pct_fci_cash_management'] == 0.0
        assert kpis['pct_portafolio_invertido'] == 50.0

    def test_top_10_concentracion(self):
        """Test cálculo de concentración top 10."""
        fecha = timezone.now()

        # Crear 12 activos con valores decrecientes
        for i in range(12):
            ActivoPortafolioSnapshot.objects.create(
                fecha_extraccion=fecha,
                pais_consulta='argentina',
                simbolo=f'ACT{i}',
                descripcion=f'Activo {i}',
                cantidad=10,
                comprometido=0,
                disponible_inmediato=10,
                puntos_variacion=0,
                variacion_diaria=0,
                ultimo_precio=100.00,
                ppc=100.00,
                ganancia_porcentaje=0,
                ganancia_dinero=0,
                valorizado=1000 - i * 50,  # Valores: 1000, 950, 900, ..., 450
                pais_titulo='Argentina',
                mercado='BCBA',
                tipo='ACCIONES',
                moneda='ARS',
            )

        kpis = get_dashboard_kpis()

        # Top 10 deberían sumar: 1000+950+900+850+800+750+700+650+600+550 = 7750
        # Total portafolio = suma de todos (12 activos) = 7750 + 500 + 450 = 8700
        # Top 10 concentración = 7750/8700 ≈ 89.08%
        assert abs(kpis['top_10_concentracion'] - 89.08) < 0.01

    def test_concentracion_por_pais(self):
        """Test cálculo de concentración por país."""
        fecha = timezone.now()

        # Crear activos en diferentes países
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=10,
            valorizado=1000.00,
            pais_titulo='Estados Unidos',
            tipo='ACCIONES',
            moneda='USD',
        )
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            simbolo='YPF',
            descripcion='YPF SA',
            cantidad=10,
            valorizado=500.00,
            pais_titulo='Argentina',
            tipo='ACCIONES',
            moneda='ARS',
        )

        concentracion = get_concentracion_pais()

        # Estados Unidos: 1000/1500 = 66.67%
        # Argentina: 500/1500 = 33.33%
        assert abs(concentracion['Estados Unidos'] - 66.67) < 0.01
        assert abs(concentracion['Argentina'] - 33.33) < 0.01

    def test_concentracion_por_tipo_patrimonial(self):
        """Test cálculo de concentración por tipo patrimonial."""
        fecha = timezone.now()

        # Crear parámetro para activo
        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )

        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=10,
            valorizado=1000.00,
            tipo='ACCIONES',
            moneda='USD',
        )

        concentracion = get_concentracion_tipo_patrimonial()
        assert 'Growth' in concentracion
        assert concentracion['Growth'] == 100.0

    def test_distribucion_moneda_vs_moneda_operativa(self):
        """Test diferencia entre exposición económica vs operativa."""
        fecha = timezone.now()

        # Crear parámetro para CEDEAR (exposición económica USD, operativa ARS)
        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )

        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            simbolo='AAPL',  # CEDEAR
            descripcion='Apple Inc',
            cantidad=10,
            valorizado=1000.00,
            tipo='CEDEARS',
            moneda='peso_Argentino',  # Operativa en ARS
        )

        # Moneda económica (exposición real)
        distribucion_economica = get_distribucion_moneda()
        assert distribucion_economica['USD'] == 1000.00  # Exposición real USD

        # Moneda operativa (cotización)
        distribucion_operativa = get_distribucion_moneda_operativa()
        assert distribucion_operativa['ARS'] == 1000.00  # Cotiza en ARS

    def test_senales_rebalanceo_objetivos(self):
        """Test señales de rebalanceo basadas en objetivos."""
        fecha = timezone.now()

        # Crear parámetros para activos
        ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Inversión',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )

        # Crear activos que excedan objetivos
        ActivoPortafolioSnapshot.objects.create(
            fecha_extraccion=fecha,
            simbolo='AAPL',
            descripcion='Apple Inc',
            cantidad=100,  # Valor alto para superar objetivos
            valorizado=20000.00,  # Tecnología objetivo 17.5%, esto sería >17.5%
            tipo='CEDEARS',
            moneda='peso_Argentino',
        )

        # Crear cash para liquidez
        ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=fecha,
            numero_cuenta='123',
            tipo_cuenta='CA',
            moneda='ARS',
            disponible=50000.00,  # Alta liquidez
        )

        senales = get_senales_rebalanceo()

        # Debería haber señales de sobreponderación
        assert len(senales['sectorial_sobreponderado']) > 0 or len(senales['patrimonial_sobreponderado']) > 0

        # Verificar estructura de señales
        for senal in senales['sectorial_sobreponderado'] + senales['sectorial_subponderado']:
            assert 'categoria' in senal or 'sector' in senal
            assert 'porcentaje' in senal
            assert 'objetivo' in senal
            assert 'diferencia' in senal

    def test_evolucion_historica_fallback(self):
        """Test que evolución histórica muestra mensaje cuando no hay datos suficientes."""
        evolucion = get_evolucion_historica()

        # Sin datos históricos, debería mostrar mensaje
        assert not evolucion['tiene_datos']
        assert 'mensaje' in evolucion
        assert 'Aún no hay historial suficiente' in evolucion['mensaje']

    def test_analytics_mensual_calculos(self):
        """Test cálculos de analytics mensual."""
        fecha = timezone.now()

        # Crear datos históricos para analytics
        for i in range(3):  # Crear datos para algunos meses
            fecha_mes = fecha.replace(month=fecha.month - i, day=1)

            ActivoPortafolioSnapshot.objects.create(
                fecha_extraccion=fecha_mes,
                simbolo='AAPL',
                descripcion='Apple Inc',
                cantidad=10,
                valorizado=1000.00 + i * 100,  # Valor creciente
                tipo='CEDEARS',
                moneda='peso_Argentino',
            )

        analytics = get_analytics_mensual()

        # Debería tener datos de analytics
        assert isinstance(analytics, dict)
        assert len(analytics) > 0  # Al menos algún cálculo