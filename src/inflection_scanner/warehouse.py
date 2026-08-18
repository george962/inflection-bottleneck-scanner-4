from __future__ import annotations

import json
import sqlite3
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .db import connect

WAREHOUSE_SCHEMA_VERSION = "5.4.1"


class ResearchWarehouse:
    """SQLite warehouse with in-place migration from the V5.3 layout.

    V5.3 used `price_daily`, a compressed `json_cache`, and a compressed
    `research_reports` table. V5.4 introduced new table shapes but originally
    relied on CREATE TABLE IF NOT EXISTS, which cannot alter an existing table.
    V5.4.1 explicitly migrates compatible history and preserves legacy tables.
    """

    def __init__(self, path: str | Path = "data/warehouse.db"):
        self.path = Path(path)
        self.con = connect(self.path)
        self.migration = self._init_schema_and_migrate()

    def _init_schema_and_migrate(self) -> dict[str, Any]:
        migration: dict[str, Any] = {
            "schema_version": WAREHOUSE_SCHEMA_VERSION,
            "migrated_price_rows": 0,
            "migrated_research_reports": 0,
            "legacy_tables": [],
        }
        self.con.execute(
            "CREATE TABLE IF NOT EXISTS warehouse_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        prior_row = self.con.execute(
            "SELECT value FROM warehouse_meta WHERE key='schema_version'"
        ).fetchone()
        prior_version = str(prior_row[0]) if prior_row else None
        migration["from_schema_version"] = prior_version

        # V5.4+ canonical daily-price table.
        self.con.executescript(
            """
            CREATE TABLE IF NOT EXISTS prices (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                PRIMARY KEY (ticker, date)
            );
            CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
            """
        )

        # Import V5.3 price history once. Keep the old table as an audit/fallback
        # source rather than destructively dropping it.
        if self._table_exists("price_daily"):
            migration["legacy_tables"].append("price_daily")
            if prior_version != WAREHOUSE_SCHEMA_VERSION:
                before = self.con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
                self.con.execute(
                    """
                    INSERT OR IGNORE INTO prices(ticker,date,open,high,low,close,volume)
                    SELECT ticker,date,open,high,low,close,volume FROM price_daily
                    """
                )
                after = self.con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
                migration["migrated_price_rows"] = int(after - before)

        self._ensure_json_cache(migration)
        self._ensure_research_reports(migration)

        self.con.execute(
            "INSERT OR REPLACE INTO warehouse_meta(key,value) VALUES('schema_version',?)",
            (WAREHOUSE_SCHEMA_VERSION,),
        )
        self.con.commit()
        return migration

    def _table_exists(self, name: str) -> bool:
        row = self.con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return row is not None

    def _columns(self, name: str) -> set[str]:
        if not self._table_exists(name):
            return set()
        return {str(r[1]) for r in self.con.execute(f'PRAGMA table_info("{name}")').fetchall()}

    def _legacy_name(self, base: str) -> str:
        if not self._table_exists(base):
            return base
        i = 2
        while self._table_exists(f"{base}_{i}"):
            i += 1
        return f"{base}_{i}"

    def _ensure_json_cache(self, migration: dict[str, Any]) -> None:
        expected = {"cache_key", "payload", "fetched_at", "expires_at"}
        cols = self._columns("json_cache")
        if cols and not expected.issubset(cols):
            legacy = self._legacy_name("legacy_json_cache_v53")
            self.con.execute(f'ALTER TABLE json_cache RENAME TO "{legacy}"')
            migration["legacy_tables"].append(legacy)
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS json_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                expires_at TEXT
            )
            """
        )

    def _ensure_research_reports(self, migration: dict[str, Any]) -> None:
        expected = {"ticker", "asof", "action", "score", "model_version", "report_json"}
        cols = self._columns("research_reports")
        legacy: str | None = None
        if cols and not expected.issubset(cols):
            legacy = self._legacy_name("legacy_research_reports_v53")
            self.con.execute(f'ALTER TABLE research_reports RENAME TO "{legacy}"')
            migration["legacy_tables"].append(legacy)

        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS research_reports (
                ticker TEXT NOT NULL,
                asof TEXT NOT NULL,
                action TEXT,
                score REAL,
                model_version TEXT NOT NULL,
                report_json TEXT NOT NULL,
                PRIMARY KEY (ticker, asof, model_version)
            )
            """
        )
        self.con.execute(
            "CREATE INDEX IF NOT EXISTS idx_research_reports_model_asof ON research_reports(model_version,asof)"
        )
        if legacy:
            migration["migrated_research_reports"] = self._import_legacy_research_reports(legacy)

    def _import_legacy_research_reports(self, table: str) -> int:
        cols = self._columns(table)
        if "payload_zlib" not in cols:
            return 0
        rows = self.con.execute(f'SELECT * FROM "{table}"').fetchall()
        imported = 0
        for row in rows:
            try:
                payload = json.loads(zlib.decompress(row["payload_zlib"]).decode("utf-8"))
                ticker = str(payload.get("ticker") or row["ticker"]).upper()
                asof = str(payload.get("asof") or row["asof"])
                version = str(payload.get("model_version") or "5.3")
                conviction = payload.get("conviction") or {}
                action = str(conviction.get("action") or row["decision"] or "UNKNOWN")
                score = _f(conviction.get("conviction_score"))
                self.con.execute(
                    """
                    INSERT OR IGNORE INTO research_reports
                    (ticker,asof,action,score,model_version,report_json)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (ticker, asof, action, score, version, json.dumps(payload, default=_json_default)),
                )
                imported += int(self.con.execute("SELECT changes()").fetchone()[0] > 0)
            except Exception:
                # The untouched legacy table remains available even if one row
                # cannot be decoded, so migration is non-destructive.
                continue
        return imported

    def schema_version(self) -> str | None:
        row = self.con.execute(
            "SELECT value FROM warehouse_meta WHERE key='schema_version'"
        ).fetchone()
        return str(row[0]) if row else None

    def close(self) -> None:
        self.con.close()

    def upsert_prices(self, ticker: str, df: pd.DataFrame) -> int:
        if df is None or df.empty:
            return 0
        rows = []
        for idx, row in df.iterrows():
            dt = pd.Timestamp(idx).date().isoformat()
            rows.append(
                (
                    ticker.upper(), dt, _f(row.get("Open")), _f(row.get("High")),
                    _f(row.get("Low")), _f(row.get("Close")), _f(row.get("Volume")),
                )
            )
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
            sql += " AND date>=?"
            params.append(start)
        if end:
            sql += " AND date<=?"
            params.append(end)
        sql += " ORDER BY date"
        rows = self.con.execute(sql, params).fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df.index = pd.to_datetime(df.pop("date"))
        df.columns = [c.title() for c in df.columns]
        return df

    def price_near_date(self, ticker: str, target_date: str, max_days: int = 10) -> float | None:
        # Limit the search window so a missing/delisted security does not match a
        # price arbitrarily far after the requested horizon.
        target = pd.Timestamp(target_date)
        end = (target + pd.Timedelta(days=max_days)).date().isoformat()
        row = self.con.execute(
            "SELECT close FROM prices WHERE ticker=? AND date>=? AND date<=? ORDER BY date LIMIT 1",
            (ticker.upper(), target.date().isoformat(), end),
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
        row = self.con.execute(
            "SELECT payload,fetched_at,expires_at FROM json_cache WHERE cache_key=?", (key,)
        ).fetchone()
        if not row:
            return None
        return {"payload": json.loads(row[0]), "fetched_at": row[1], "expires_at": row[2]}

    def put_research_report(self, ticker: str, asof: str, action: str, score: float | None, report: dict[str, Any]) -> None:
        version = str(report.get("model_version") or "unknown")
        self.con.execute(
            """
            INSERT OR REPLACE INTO research_reports
            (ticker,asof,action,score,model_version,report_json) VALUES (?,?,?,?,?,?)
            """,
            (ticker.upper(), asof, action, score, version, json.dumps(report, default=_json_default)),
        )
        self.con.commit()

    def list_research_reports(self, model_version: str | None = None) -> list[dict[str, Any]]:
        if model_version:
            rows = self.con.execute(
                "SELECT report_json FROM research_reports WHERE model_version=? ORDER BY asof",
                (model_version,),
            ).fetchall()
        else:
            rows = self.con.execute("SELECT report_json FROM research_reports ORDER BY asof").fetchall()
        return [json.loads(r[0]) for r in rows]

    def stats(self) -> dict[str, Any]:
        p = self.con.execute("SELECT COUNT(*),COUNT(DISTINCT ticker) FROM prices").fetchone()
        c = self.con.execute("SELECT COUNT(*) FROM json_cache").fetchone()[0]
        r = self.con.execute("SELECT COUNT(*) FROM research_reports").fetchone()[0]
        return {
            "warehouse_path": str(self.path.resolve()),
            "schema_version": self.schema_version(),
            "migration": self.migration,
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
