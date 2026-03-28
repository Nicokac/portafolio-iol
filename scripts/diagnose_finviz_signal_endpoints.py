from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from typing import Any


DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NEM", "GOOGL", "AMZN"]
DEFAULT_OPERATIONS = ["fundamentals", "ratings", "news", "insiders"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnostica acceso real a endpoints de finvizfinance para fundamentals, "
            "ratings, news e insiders sobre un conjunto chico de simbolos."
        )
    )
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="Lista separada por comas de simbolos a consultar.",
    )
    parser.add_argument(
        "--operations",
        default=",".join(DEFAULT_OPERATIONS),
        help="Operaciones separadas por comas: fundamentals,ratings,news,insiders",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
        help="Delay entre requests para no golpear Finviz demasiado rapido.",
    )
    return parser


def _normalize_list(raw: str) -> list[str]:
    return [item.strip().upper() for item in str(raw or "").split(",") if item.strip()]


def _import_quote_class():
    try:
        from finvizfinance.quote import finvizfinance
    except Exception as exc:  # pragma: no cover - depende del entorno
        print("[dependency]", f"ERROR: {exc}")
        raise
    return finvizfinance


def _run_operation(quote: Any, operation: str) -> tuple[str, dict[str, Any]]:
    if operation == "fundamentals":
        payload = quote.ticker_fundament()
        if not payload:
            return "empty", {"size": 0}
        return "ok", {"size": len(payload), "sample_keys": list(payload.keys())[:8]}

    if operation == "ratings":
        payload = quote.ticker_outer_ratings()
    elif operation == "news":
        payload = quote.ticker_news()
    elif operation == "insiders":
        payload = quote.ticker_inside_trader()
    else:
        return "invalid", {"message": f"unsupported operation: {operation}"}

    if payload is None:
        return "empty", {"size": 0, "kind": "none"}
    if hasattr(payload, "empty") and payload.empty:
        return "empty", {"size": 0, "kind": "dataframe"}
    if hasattr(payload, "to_dict"):
        records = payload.to_dict(orient="records")
        sample = records[0] if records else {}
        return "ok", {"size": len(records), "sample_keys": list(sample.keys())[:8]}
    if isinstance(payload, list):
        sample = payload[0] if payload else {}
        return "ok", {"size": len(payload), "sample_keys": list(getattr(sample, "keys", lambda: [])())[:8]}
    return "ok", {"size": 1, "kind": type(payload).__name__}


def main() -> int:
    args = _build_parser().parse_args()
    symbols = _normalize_list(args.symbols)
    operations = [item.strip().lower() for item in str(args.operations or "").split(",") if item.strip()]

    print("[setup]", f"symbols={symbols}")
    print("[setup]", f"operations={operations}")

    try:
        finvizfinance = _import_quote_class()
    except Exception:
        return 2

    counters: Counter[str] = Counter()
    failures: list[dict[str, str]] = []

    for symbol in symbols:
        print(f"\n[symbol] {symbol}")
        for operation in operations:
            try:
                quote = finvizfinance(symbol)
                status, detail = _run_operation(quote, operation)
            except Exception as exc:
                status = "error"
                detail = {"message": str(exc), "error_type": type(exc).__name__}
                failures.append(
                    {
                        "symbol": symbol,
                        "operation": operation,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )

            counters[f"{operation}:{status}"] += 1
            print(f"  - {operation}: {status} | {detail}")
            time.sleep(max(0.0, args.delay))

    print("\n[summary]")
    for operation in operations:
        op_counts = {
            "ok": counters.get(f"{operation}:ok", 0),
            "empty": counters.get(f"{operation}:empty", 0),
            "error": counters.get(f"{operation}:error", 0),
            "invalid": counters.get(f"{operation}:invalid", 0),
        }
        print(f"  - {operation}: {op_counts}")

    if failures:
        print("\n[failures]")
        for failure in failures[:10]:
            print(
                f"  - {failure['symbol']}::{failure['operation']} | "
                f"{failure['error_type']} | {failure['message']}"
            )

    fundamentals_ok = counters.get("fundamentals:ok", 0)
    signal_errors = sum(counters.get(f"{op}:error", 0) for op in ("ratings", "news", "insiders"))
    signal_ok = sum(counters.get(f"{op}:ok", 0) for op in ("ratings", "news", "insiders"))

    print("\n[diagnosis]")
    if fundamentals_ok > 0 and signal_errors == 0 and signal_ok > 0:
        print("  - La libreria y la conectividad hacia Finviz parecen sanas para fundamentals y overlays secundarios.")
    elif fundamentals_ok > 0 and signal_errors > 0:
        print("  - Fundamentals responden, pero hay fallas en ratings/news/insiders. Esto apunta a un problema especifico de endpoint o conectividad parcial.")
    elif fundamentals_ok == 0 and signal_errors > 0:
        print("  - Fallan fundamentals y overlays secundarios. Esto apunta a bloqueo general de conectividad, dependencia o entorno.")
    else:
        print("  - No hubo suficiente evidencia para cerrar el diagnostico. Revisar detalles arriba.")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
