from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .db import connect


class ResearchWarehouse:
    def __init__(self, path: str | Path = "data/warehouse.db"):
        self.path = Path(path)
        self.con = connect(self.path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.con.executescript(
            """
            CREATE TABLE IF NOT EXISTS prices (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                PRIMARY KEY (ticker, date)
            );
            CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
            CREATE TABLE IF NOT EXISTS json_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                expires_at TEXT
            );
            CREATE TABLE IF NOT EXISTS research_reports (
                ticker TEXT NOT NULL,
                asof TEXT NOT NULL,
                action TEXT,
                score REAL,
                model_version TEXT,
                report_json TEXT NOT NULL,
                PRIMARY KEY (ticker, asof, model_version)
            );
            """
        )
        self.con.commit()

    def close(self) -> None:
        self.con.close()

    def upsert_prices(self, ticker: str, df: pd.DataFrame) -> int:
        if df is None or df.empty:
            return 0
        rows = []
        for idx, row in df.iterrows():
            dt = pd.Timestamp(idx).date().isoformat()
            rows.append((ticker.upper(), dt, _f(row.get("Open")), _f(row.get("High")), _f(row.get("Low")), _f(row.get("Close")), _f(row.get("Volume"))))
        self.con.executemany(
            "INSERT OR REPLACE INTO prices(ticker,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        self.con.commit()
        return len(rows)

    def price_history(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        sql = "SELECT date,open,high,low,close,volume FROM prices WHERE ticker=?"
        params: list[Any] = [ticker.upper()]
        if start:
            sql += " AND date>=?"; params.append(start)
        if end:
            sql += " AND date<=?"; params.append(end)
        sql += " ORDER BY date"
        rows = self.con.execute(sql, params).fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df.index = pd.to_datetime(df.pop("date"))
        df.columns = [c.title() for c in df.columns]
        return df

    def price_near_date(self, ticker: str, target_date: str, max_days: int = 10) -> float | None:
        row = self.con.execute(
            "SELECT close FROM prices WHERE ticker=? AND date>=? ORDER BY date LIMIT 1",
            (ticker.upper(), target_date),
        ).fetchone()
        return float(row[0]) if row and row[0] is not None else None

    def price_window(self, ticker: str, start_date: str, end_date: str) -> list[float]:
        rows = self.con.execute(
            "SELECT close FROM prices WHERE ticker=? AND date>=? AND date<=? ORDER BY date",
            (ticker.upper(), start_date, end_date),
        ).fetchall()
        return [float(r[0]) for r in rows if r[0] is not None]

    def put_cache(self, key: str, payload: Any, expires_at: str | None = None, fetched_at: str | None = None) -> None:
        fetched_at = fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.con.execute(
            "INSERT OR REPLACE INTO json_cache(cache_key,payload,fetched_at,expires_at) VALUES (?,?,?,?)",
            (key, json.dumps(payload, default=_json_default), fetched_at, expires_at),
        )
        self.con.commit()

    def get_cache(self, key: str) -> dict[str, Any] | None:
        row = self.con.execute("SELECT payload,fetched_at,expires_at FROM json_cache WHERE cache_key=?", (key,)).fetchone()
        if not row:
            return None
        return {"payload": json.loads(row[0]), "fetched_at": row[1], "expires_at": row[2]}

    def put_research_report(self, ticker: str, asof: str, action: str, score: float | None, report: dict[str, Any]) -> None:
        version = str(report.get("model_version") or "unknown")
        self.con.execute(
            "INSERT OR REPLACE INTO research_reports(ticker,asof,action,score,model_version,report_json) VALUES (?,?,?,?,?,?)",
            (ticker.upper(), asof, action, score, version, json.dumps(report, default=_json_default)),
        )
        self.con.commit()

    def list_research_reports(self, model_version: str | None = None) -> list[dict[str, Any]]:
        if model_version:
            rows = self.con.execute("SELECT report_json FROM research_reports WHERE model_version=? ORDER BY asof", (model_version,)).fetchall()
        else:
            rows = self.con.execute("SELECT report_json FROM research_reports ORDER BY asof").fetchall()
        return [json.loads(r[0]) for r in rows]

    def stats(self) -> dict[str, Any]:
        p = self.con.execute("SELECT COUNT(*),COUNT(DISTINCT ticker) FROM prices").fetchone()
        c = self.con.execute("SELECT COUNT(*) FROM json_cache").fetchone()[0]
        r = self.con.execute("SELECT COUNT(*) FROM research_reports").fetchone()[0]
        return {
            "warehouse_path": str(self.path.resolve()),
            "price_rows": int(p[0]),
            "price_tickers": int(p[1]),
            "json_cache_entries": int(c),
            "research_reports": int(r),
            "size_mb": round(self.path.stat().st_size / 1024 / 1024, 2) if self.path.exists() else 0.0,
        }


def _f(value: Any) -> float | None:
    try:
        x = float(value)
        return x if pd.notna(x) else None
    except Exception:
        return None


def _json_default(value: Any):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        return float(value)
    except Exception:
        return str(value)
