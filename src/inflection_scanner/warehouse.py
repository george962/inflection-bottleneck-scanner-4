from __future__ import annotations

import json
import math
import sqlite3
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS price_daily(
 ticker TEXT NOT NULL,
 date TEXT NOT NULL,
 open REAL,
 high REAL,
 low REAL,
 close REAL,
 volume REAL,
 PRIMARY KEY(ticker,date)
);

CREATE INDEX IF NOT EXISTS idx_price_date ON price_daily(date);

CREATE TABLE IF NOT EXISTS fetch_state(
 cache_key TEXT PRIMARY KEY,
 fetched_at TEXT NOT NULL,
 metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS json_cache(
 cache_key TEXT PRIMARY KEY,
 fetched_at TEXT NOT NULL,
 expires_at TEXT,
 payload_zlib BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS filing_documents(
 ticker TEXT NOT NULL,
 accession TEXT NOT NULL,
 form TEXT,
 filing_date TEXT,
 report_date TEXT,
 source_url TEXT,
 fetched_at TEXT NOT NULL,
 text_zlib BLOB NOT NULL,
 PRIMARY KEY(ticker,accession)
);

CREATE INDEX IF NOT EXISTS idx_filing_date
ON filing_documents(ticker,filing_date DESC);

CREATE TABLE IF NOT EXISTS research_reports(
 ticker TEXT NOT NULL,
 asof TEXT NOT NULL,
 decision TEXT,
 expected_cagr REAL,
 payload_zlib BLOB NOT NULL,
 PRIMARY KEY(ticker,asof)
);
"""


def now():
    return datetime.now(timezone.utc)


def iso():
    return now().isoformat(timespec="seconds")


def dump(obj):
    return zlib.compress(json.dumps(obj, default=str, allow_nan=False).encode(), 6)


def load(blob):
    return json.loads(zlib.decompress(blob).decode())


class ResearchWarehouse:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def put_json(self, key, payload, ttl_hours=None):
        n = now()
        exp = (
            (n + timedelta(hours=ttl_hours)).isoformat(timespec="seconds")
            if ttl_hours is not None
            else None
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO json_cache VALUES(?,?,?,?)",
            (key, n.isoformat(timespec="seconds"), exp, dump(payload)),
        )
        self.conn.commit()

    def get_json(self, key, allow_stale=False):
        row = self.conn.execute(
            "SELECT expires_at,payload_zlib FROM json_cache WHERE cache_key=?",
            (key,),
        ).fetchone()
        if not row:
            return None
        if row["expires_at"] and not allow_stale and now() > datetime.fromisoformat(row["expires_at"]):
            return None
        return load(row["payload_zlib"])

    def cache_metadata(self, key):
        row = self.conn.execute(
            "SELECT fetched_at,expires_at FROM json_cache WHERE cache_key=?",
            (key,),
        ).fetchone()
        if not row:
            return {
                "present": False,
                "fetched_at": None,
                "expires_at": None,
                "age_hours": None,
                "stale": True,
            }
        fetched = datetime.fromisoformat(row["fetched_at"])
        expires = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
        return {
            "present": True,
            "fetched_at": row["fetched_at"],
            "expires_at": row["expires_at"],
            "age_hours": round((now() - fetched).total_seconds() / 3600.0, 2),
            "stale": bool(expires and now() > expires),
        }

    def set_fetch_state(self, key, metadata=None):
        self.conn.execute(
            "INSERT OR REPLACE INTO fetch_state VALUES(?,?,?)",
            (key, iso(), json.dumps(metadata or {})),
        )
        self.conn.commit()

    def get_fetch_state(self, key):
        row = self.conn.execute(
            "SELECT fetched_at,metadata_json FROM fetch_state WHERE cache_key=?",
            (key,),
        ).fetchone()
        return {
            "fetched_at": row["fetched_at"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
        } if row else None

    def is_fetch_fresh(self, key, max_age_hours):
        state = self.get_fetch_state(key)
        return bool(
            state
            and now() - datetime.fromisoformat(state["fetched_at"])
            <= timedelta(hours=max_age_hours)
        )

    def known_price_tickers(self):
        return {row["ticker"] for row in self.conn.execute("SELECT DISTINCT ticker FROM price_daily")}

    def upsert_prices(self, ticker, df):
        if df is None or df.empty or "Close" not in df:
            return 0
        records = []
        for idx, row in df.iterrows():
            try:
                date = pd.Timestamp(idx).date().isoformat()
            except Exception:
                continue

            def num(k):
                try:
                    x = float(row.get(k))
                    return x if math.isfinite(x) else None
                except Exception:
                    return None

            records.append(
                (
                    ticker.upper(),
                    date,
                    num("Open"),
                    num("High"),
                    num("Low"),
                    num("Close"),
                    num("Volume"),
                )
            )
        if records:
            self.conn.executemany(
                "INSERT OR REPLACE INTO price_daily VALUES(?,?,?,?,?,?,?)",
                records,
            )
            self.conn.commit()
        return len(records)

    def load_prices(self, ticker, limit=600):
        rows = self.conn.execute(
            "SELECT date,open,high,low,close,volume FROM price_daily WHERE ticker=? ORDER BY date DESC LIMIT ?",
            (ticker.upper(), limit),
        ).fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in reversed(rows)])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df.columns = ["Open", "High", "Low", "Close", "Volume"]
        return df

    def latest_price_date(self, ticker):
        row = self.conn.execute(
            "SELECT MAX(date) AS d FROM price_daily WHERE ticker=?",
            (ticker.upper(),),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    def delete_prices_older_than(self, days=900):
        cutoff = (now() - timedelta(days=days)).date().isoformat()
        self.conn.execute("DELETE FROM price_daily WHERE date<?", (cutoff,))
        self.conn.commit()

    def has_filing(self, ticker, accession):
        return self.conn.execute(
            "SELECT 1 FROM filing_documents WHERE ticker=? AND accession=?",
            (ticker.upper(), accession),
        ).fetchone() is not None

    def put_filing(self, ticker, accession, form, filing_date, report_date, source_url, text):
        self.conn.execute(
            "INSERT OR REPLACE INTO filing_documents VALUES(?,?,?,?,?,?,?,?)",
            (
                ticker.upper(),
                accession,
                form,
                filing_date,
                report_date,
                source_url,
                iso(),
                zlib.compress(text.encode(), 6),
            ),
        )
        self.conn.commit()

    def recent_filings(self, ticker, limit=10):
        rows = self.conn.execute(
            "SELECT * FROM filing_documents WHERE ticker=? ORDER BY filing_date DESC LIMIT ?",
            (ticker.upper(), limit),
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["text"] = zlib.decompress(d.pop("text_zlib")).decode()
            out.append(d)
        return out

    def put_research_report(self, ticker, asof, decision, expected_cagr, payload):
        self.conn.execute(
            "INSERT OR REPLACE INTO research_reports VALUES(?,?,?,?,?)",
            (ticker.upper(), asof, decision, expected_cagr, dump(payload)),
        )
        self.conn.commit()

    def latest_research_report(self, ticker):
        row = self.conn.execute(
            "SELECT payload_zlib FROM research_reports WHERE ticker=? ORDER BY asof DESC LIMIT 1",
            (ticker.upper(),),
        ).fetchone()
        return load(row["payload_zlib"]) if row else None

    def list_research_reports(self, model_version=None):
        rows = self.conn.execute(
            "SELECT payload_zlib FROM research_reports ORDER BY asof ASC"
        ).fetchall()
        reports = [load(row["payload_zlib"]) for row in rows]
        if model_version is not None:
            reports = [r for r in reports if str(r.get("model_version")) == str(model_version)]
        return reports

    def price_near_date(self, ticker, target_date, max_days=10):
        row = self.conn.execute(
            """
            SELECT close FROM price_daily
            WHERE ticker=? AND date>=? AND date<=date(?, '+' || ? || ' day')
            ORDER BY date ASC LIMIT 1
            """,
            (ticker.upper(), target_date, target_date, int(max_days)),
        ).fetchone()
        if row and row["close"] is not None:
            return float(row["close"])
        row = self.conn.execute(
            """
            SELECT close FROM price_daily
            WHERE ticker=? AND date<=? AND date>=date(?, '-' || ? || ' day')
            ORDER BY date DESC LIMIT 1
            """,
            (ticker.upper(), target_date, target_date, int(max_days)),
        ).fetchone()
        return float(row["close"]) if row and row["close"] is not None else None

    def cache_info(self):
        q = lambda sql: int(self.conn.execute(sql).fetchone()[0])
        return {
            "warehouse_path": str(self.path),
            "json_cache_entries": q("SELECT COUNT(*) FROM json_cache"),
            "price_rows": q("SELECT COUNT(*) FROM price_daily"),
            "price_tickers": q("SELECT COUNT(DISTINCT ticker) FROM price_daily"),
            "filing_documents": q("SELECT COUNT(*) FROM filing_documents"),
            "research_reports": q("SELECT COUNT(*) FROM research_reports"),
            "size_mb": round(self.path.stat().st_size / 1024 / 1024, 2) if self.path.exists() else 0.0,
        }
