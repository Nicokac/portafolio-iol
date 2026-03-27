from django.core.management.base import BaseCommand

from apps.core.services.iol_historical_price_service import IOLHistoricalPriceService


class Command(BaseCommand):
    help = "Sincroniza historicos IOL para simbolos actuales o un simbolo puntual"

    def add_arguments(self, parser):
        parser.add_argument("--simbolo", help="Simbolo puntual a sincronizar")
        parser.add_argument("--mercado", help="Mercado del simbolo puntual")
        parser.add_argument(
            "--statuses",
            nargs="+",
            help="Estados de cobertura a sincronizar dentro del portfolio actual (ej: missing partial unsupported)",
        )
        parser.add_argument(
            "--eligibility-reason-keys",
            nargs="+",
            dest="eligibility_reason_keys",
            help="Filtra exclusiones por reason_key al usar --statuses (ej: title_metadata_unresolved)",
        )

    def handle(self, *args, **options):
        service = IOLHistoricalPriceService()
        simbolo = options.get("simbolo")
        mercado = options.get("mercado")
        statuses = tuple(options.get("statuses") or ())
        eligibility_reason_keys = tuple(options.get("eligibility_reason_keys") or ())

        self.stdout.write("Sincronizando historicos IOL...")

        if simbolo or mercado:
            if not simbolo or not mercado:
                raise SystemExit("Debe informar ambos parametros: --simbolo y --mercado")
            if statuses or eligibility_reason_keys:
                raise SystemExit("No se puede combinar --simbolo/--mercado con --statuses o --eligibility-reason-keys")
            result = service.sync_symbol_history(mercado=mercado, simbolo=simbolo)
            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {mercado}:{simbolo}: created={result['created']} updated={result['updated']} rows={result['rows_received']}"
                    )
                )
                self.stdout.write(self.style.SUCCESS("Sincronizacion de historicos IOL completada"))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {mercado}:{simbolo}: error={result.get('error', 'unknown')} rows={result.get('rows_received', 0)}"
                    )
                )
                self.stdout.write(self.style.WARNING("Sincronizacion de historicos IOL completada con fallos"))
            return

        if eligibility_reason_keys and not statuses:
            raise SystemExit("Debe informar --statuses cuando usa --eligibility-reason-keys")

        if statuses:
            result = service.sync_current_portfolio_symbols_by_status(
                statuses=statuses,
                eligibility_reason_keys=eligibility_reason_keys or None,
            )
            has_partial_failures = False
            for key, payload in result.get("results", {}).items():
                if payload.get("success"):
                    self.stdout.write(
                        f"  {key}: created={payload.get('created', 0)} updated={payload.get('updated', 0)} rows={payload['rows_received']}"
                    )
                else:
                    has_partial_failures = True
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {key}: error={payload.get('error', 'unknown')} rows={payload.get('rows_received', 0)}"
                        )
                    )

            selected_count = int(result.get("selected_count") or 0)
            if selected_count == 0:
                self.stdout.write(
                    self.style.WARNING(
                        "Sincronizacion de historicos IOL sin simbolos seleccionados para los filtros indicados"
                    )
                )
                return

            if result.get("success", True) and not has_partial_failures:
                self.stdout.write(self.style.SUCCESS("Sincronizacion de historicos IOL completada"))
            else:
                self.stdout.write(self.style.WARNING("Sincronizacion de historicos IOL completada con fallos parciales"))
            return

        result = service.sync_current_portfolio_symbols()
        has_partial_failures = False
        for key, payload in result.get("results", {}).items():
            if payload.get("success"):
                self.stdout.write(
                    f"  {key}: created={payload['created']} updated={payload['updated']} rows={payload['rows_received']}"
                )
            else:
                has_partial_failures = True
                self.stdout.write(
                    self.style.WARNING(
                        f"  {key}: error={payload.get('error', 'unknown')} rows={payload.get('rows_received', 0)}"
                    )
                )

        if result.get("success", True) and not has_partial_failures:
            self.stdout.write(self.style.SUCCESS("Sincronizacion de historicos IOL completada"))
        else:
            self.stdout.write(self.style.WARNING("Sincronizacion de historicos IOL completada con fallos parciales"))
