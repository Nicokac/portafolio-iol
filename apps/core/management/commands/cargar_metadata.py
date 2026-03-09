from django.core.management.base import BaseCommand
from apps.parametros.models import ParametroActivo


class Command(BaseCommand):
    help = 'Carga metadata inicial para ParametroActivo'

    def handle(self, *args, **options):
        # Metadata inicial proporcionada por el usuario
        metadata = [
            # CEDEAR tecnología
            {'simbolo': 'AAPL', 'sector': 'Tecnología', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'MSFT', 'sector': 'Tecnología', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'GOOGL', 'sector': 'Tecnología', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'NVDA', 'sector': 'Tecnología', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'CRM', 'sector': 'Tecnología', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'AMZN', 'sector': 'Consumo', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},

            # ETFs
            {'simbolo': 'SPY', 'sector': 'Índice', 'bloque_estrategico': 'Core', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'ETF'},
            {'simbolo': 'EEM', 'sector': 'Índice', 'bloque_estrategico': 'Emergentes', 'pais_exposicion': 'EM', 'tipo_patrimonial': 'ETF'},
            {'simbolo': 'EWZ', 'sector': 'Índice', 'bloque_estrategico': 'Brasil', 'pais_exposicion': 'Brasil', 'tipo_patrimonial': 'ETF'},
            {'simbolo': 'IEUR', 'sector': 'Índice', 'bloque_estrategico': 'Europa', 'pais_exposicion': 'Europa', 'tipo_patrimonial': 'ETF'},
            {'simbolo': 'XLU', 'sector': 'Utilities', 'bloque_estrategico': 'Defensivo', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'ETF'},
            {'simbolo': 'XLV', 'sector': 'Salud', 'bloque_estrategico': 'Defensivo', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'ETF'},
            {'simbolo': 'DIA', 'sector': 'Índice', 'bloque_estrategico': 'Core', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'ETF'},

            # Commodities / minería
            {'simbolo': 'NEM', 'sector': 'Minería', 'bloque_estrategico': 'Commodities', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},

            # Argentina acciones
            {'simbolo': 'YPFD', 'sector': 'Energía', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'TECO2', 'sector': 'Telecom', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'LOMA', 'sector': 'Materiales', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Equity'},

            # Bonos
            {'simbolo': 'AL30', 'sector': 'Soberano', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Bond'},
            {'simbolo': 'GD30', 'sector': 'Soberano', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Bond'},
            {'simbolo': 'GD35', 'sector': 'Soberano', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Bond'},
            {'simbolo': 'TZX26', 'sector': 'CER', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Bond'},
            {'simbolo': 'TZXM6', 'sector': 'CER', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Bond'},
            {'simbolo': 'BPOC7', 'sector': 'Corporativo', 'bloque_estrategico': 'Argentina', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Bond'},

            # FCI
            {'simbolo': 'ADBAICA', 'sector': 'Cash Mgmt', 'bloque_estrategico': 'Liquidez', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'FCI'},
            {'simbolo': 'IOLPORA', 'sector': 'Cash Mgmt', 'bloque_estrategico': 'Liquidez', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'FCI'},
            {'simbolo': 'PRPEDOB', 'sector': 'Cash Mgmt', 'bloque_estrategico': 'USD', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'FCI'},

            # Liquidez
            {'simbolo': 'CAUCIÓN', 'sector': 'Liquidez', 'bloque_estrategico': 'Liquidez', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Cash'},
            {'simbolo': 'CAUCIÓN COLOCADORA', 'sector': 'Liquidez', 'bloque_estrategico': 'Liquidez', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Cash'},

            # Activos adicionales faltantes
            {'simbolo': 'T', 'sector': 'Telecom', 'bloque_estrategico': 'Dividendos', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'MELI', 'sector': 'Tecnología / E-commerce', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'Latam', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'KO', 'sector': 'Consumo defensivo', 'bloque_estrategico': 'Dividendos', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'VIST', 'sector': 'Energía', 'bloque_estrategico': 'Commodities', 'pais_exposicion': 'Argentina', 'tipo_patrimonial': 'Equity'},

            # Nuevos activos faltantes según requerimiento P1.1
            {'simbolo': 'V', 'sector': 'Finanzas / Payments', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'BRKB', 'sector': 'Finanzas / Holding', 'bloque_estrategico': 'Defensivo', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'MCD', 'sector': 'Consumo defensivo', 'bloque_estrategico': 'Dividendos', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'DISN', 'sector': 'Consumo / Media', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'BABA', 'sector': 'Tecnología / E-commerce', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'China', 'tipo_patrimonial': 'Equity'},
            {'simbolo': 'AMD', 'sector': 'Tecnología / Semiconductores', 'bloque_estrategico': 'Growth', 'pais_exposicion': 'USA', 'tipo_patrimonial': 'Equity'},
        ]

        created_count = 0
        updated_count = 0

        for item in metadata:
            obj, created = ParametroActivo.objects.update_or_create(
                simbolo=item['simbolo'],
                defaults={
                    'sector': item['sector'],
                    'bloque_estrategico': item['bloque_estrategico'],
                    'pais_exposicion': item['pais_exposicion'],
                    'tipo_patrimonial': item['tipo_patrimonial'],
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'Creado: {item["simbolo"]}')
            else:
                updated_count += 1
                self.stdout.write(f'Actualizado: {item["simbolo"]}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Carga completada: {created_count} creados, {updated_count} actualizados'
            )
        )