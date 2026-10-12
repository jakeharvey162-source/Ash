"""Read-only BROBS trading journal report for OWNER-EXPORTED CSV statements.

This is not a live brokerage connection or a performance prediction.
"""
from __future__ import annotations
import csv
import datetime as dt
import decimal
import pathlib

_COLUMNS = {"symbol", "side", "status", "realized_pnl"}
MAX_BYTES = 400_000
MAX_ROWS = 4000


def analyze_statement(path: str | pathlib.Path) -> dict:
    source = pathlib.Path(path)
    if not source.is_file() or source.suffix.lower() != ".csv":
        raise ValueError("Choose a CSV trade statement exported from your broker.")
    if source.stat().st_size > MAX_BYTES:
        raise ValueError("This export is too large for local review.")
    trades = []
    opened = 0
    with source.open("r", encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        if not rows.fieldnames or not _COLUMNS.issubset(set(rows.fieldnames)):
            raise ValueError("Statement needs symbol, side, status and realized_pnl columns.")
        for index, row in enumerate(rows):
            if index >= MAX_ROWS:
                raise ValueError("Statement has too many trades.")
            symbol = str(row.get("symbol") or "").strip()
            side = str(row.get("side") or "").strip().lower()
            status = str(row.get("status") or "").strip().lower()
            if not symbol or len(symbol)>40 or side not in ("buy","sell","long","short"):
                raise ValueError("Invalid symbol or trade direction.")
            if status in ("open","pending"):
                opened += 1
                continue
            if status != "closed":
                raise ValueError("Unexpected trade status; cannot calculate reliable results.")
            value = str(row.get("realized_pnl") or "").strip()
            try:
                pnl = decimal.Decimal(value)
                if not pnl.is_finite() or abs(pnl)>decimal.Decimal("1000000000000"):
                    raise ValueError()
            except (decimal.InvalidOperation, ValueError):
                raise ValueError("A closed trade has invalid realized P&L.") from None
            trades.append(pnl)
    winners = sum(1 for p in trades if p>0)
    losers = sum(1 for p in trades if p<0)
    breakeven = len(trades)-winners-losers
    gross_profit = sum((p for p in trades if p>0), decimal.Decimal(0))
    gross_loss = sum((p for p in trades if p<0), decimal.Decimal(0))
    net = sum(trades, decimal.Decimal(0))
    def money(amount):
        return str(amount.quantize(decimal.Decimal("0.01")))
    return {
        "source_type": "user_imported_csv_not_live_broker",
        "source_file": source.name,
        "analyzed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "currency": "from_export_not_verified",
        "closed_count": len(trades),
        "open_count": opened,
        "wins": winners, "losses": losers, "breakeven": breakeven,
        "win_rate_percent": round(100 * winners / len(trades),2) if trades else None,
        "net_realized_pnl": money(net),
        "gross_profit": money(gross_profit),
        "gross_loss": money(gross_loss),
        "profit_factor": round(float(gross_profit / abs(gross_loss)),3) if gross_loss else None,
        "worst_closed_trade": money(min(trades)) if trades else None,
        "warning": "Historical exported results only. No live prices, trade execution, broker verification, predictions or guaranteed future returns.",
    }
