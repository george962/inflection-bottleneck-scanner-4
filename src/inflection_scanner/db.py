from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    universe_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapshots (
    run_id INTEGER NOT NULL,
    asof TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company TEXT,
    sector TEXT,
    industry TEXT,
    themes TEXT,

    total_score REAL,
    opportunity_score REAL,
    strength_score REAL,
    fundamental_score REAL,
    revisions_score REAL,
    scarcity_score REAL,
    operating_leverage_score REAL,
    demand_score REAL,
    valuation_score REAL,
    market_score REAL,
    expectation_gap_score REAL,
    confirmation_score REAL,
    extension_penalty REAL,
    weighted_coverage REAL,

    potential_score REAL,
    forward_growth_score REAL,
    valuation_upside_score REAL,
    early_discovery_score REAL,
    price_maturity_score REAL,

    stage TEXT,
    action TEXT,
    already_priced TEXT,
    price_stage TEXT,
    source TEXT,
    score_delta_last REAL,

    data_quality REAL,
    error TEXT,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (run_id, ticker),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_asof
ON snapshots(ticker, asof);

CREATE INDEX IF NOT EXISTS idx_snapshots_score
ON snapshots(total_score DESC);
"""


MIGRATION_COLUMNS = {
    "potential_score": "REAL",
    "forward_growth_score": "REAL",
    "valuation_upside_score": "REAL",
    "early_discovery_score": "REAL",
    "price_maturity_score": "REAL",
    "price_stage": "TEXT",
    "source": "TEXT",
    "opportunity_score": "REAL",
    "strength_score": "REAL",
    "expectation_gap_score": "REAL",
    "confirmation_score": "REAL",
    "extension_penalty": "REAL",
    "weighted_coverage": "REAL",
    "stage": "TEXT",
    "action": "TEXT",
    "already_priced": "TEXT",
    "score_delta_last": "REAL",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(snapshots)").fetchall()
        }
        for name, sql_type in MIGRATION_COLUMNS.items():
            if name not in columns:
                self.conn.execute(
                    f"ALTER TABLE snapshots ADD COLUMN {name} {sql_type}"
                )

    def close(self) -> None:
        self.conn.close()

    def start_run(self, universe_count: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs(started_at,status,universe_count) VALUES(?,?,?)",
            (utc_now_iso(), "running", universe_count),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, success_count: int, failure_count: int) -> None:
        status = "ok" if failure_count == 0 else "partial"
        self.conn.execute(
            """
            UPDATE runs
            SET finished_at=?, status=?, success_count=?, failure_count=?
            WHERE id=?
            """,
            (utc_now_iso(), status, success_count, failure_count, run_id),
        )
        self.conn.commit()

    def save_snapshot(self, run_id: int, snapshot: dict[str, Any]) -> None:
        scores = snapshot.get("scores", {})
        assessment = snapshot.get("assessment", {})
        self.conn.execute(
            """
            INSERT OR REPLACE INTO snapshots(
                run_id, asof, ticker, company, sector, industry, themes,
                total_score, opportunity_score, strength_score,
                fundamental_score, revisions_score, scarcity_score,
                operating_leverage_score, demand_score, valuation_score,
                market_score, expectation_gap_score, confirmation_score,
                extension_penalty, weighted_coverage,
                potential_score, forward_growth_score, valuation_upside_score,
                early_discovery_score, price_maturity_score,
                stage, action, already_priced, price_stage, source,
                score_delta_last, data_quality, error, payload_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                snapshot.get("asof"),
                snapshot.get("ticker"),
                snapshot.get("company"),
                snapshot.get("sector"),
                snapshot.get("industry"),
                json.dumps(snapshot.get("themes", [])),

                scores.get("total"),
                scores.get("total"),
                None,
                scores.get("fundamental"),
                scores.get("revisions"),
                None,
                scores.get("operating_leverage"),
                None,
                scores.get("valuation_upside"),
                None,
                scores.get("expectation_gap"),
                None,
                scores.get("extension_penalty_points"),
                scores.get("weighted_coverage"),

                scores.get("total"),
                scores.get("forward_growth"),
                scores.get("valuation_upside"),
                scores.get("early_discovery"),
                scores.get("price_maturity"),

                assessment.get("stage"),
                assessment.get("action"),
                None,
                assessment.get("price_stage"),
                snapshot.get("source"),
                assessment.get("score_delta_last"),

                snapshot.get("data_quality"),
                snapshot.get("error"),
                json.dumps(snapshot, default=str, allow_nan=False),
            ),
        )
        self.conn.commit()

    def latest_run_id(self) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM runs WHERE status IN ('ok','partial') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return int(row["id"]) if row else None

    def latest_rankings(self, limit: int = 50) -> list[dict[str, Any]]:
        run_id = self.latest_run_id()
        if run_id is None:
            return []
        rows = self.conn.execute(
            """
            SELECT * FROM snapshots
            WHERE run_id=? AND error IS NULL
            ORDER BY COALESCE(potential_score,total_score) DESC, ticker ASC
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def latest_snapshot(self, ticker: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT payload_json FROM snapshots
            WHERE ticker=? AND error IS NULL
            ORDER BY run_id DESC LIMIT 1
            """,
            (ticker.upper(),),
        ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def latest_snapshot_before_run(
        self,
        ticker: str,
        run_id: int,
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT payload_json FROM snapshots
            WHERE ticker=? AND error IS NULL AND run_id < ?
            ORDER BY run_id DESC LIMIT 1
            """,
            (ticker.upper(), run_id),
        ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def score_history(self, ticker: str, limit: int = 90) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT asof,
                   COALESCE(potential_score,total_score) AS potential_score,
                   fundamental_score,revisions_score,
                   operating_leverage_score,forward_growth_score,
                   valuation_upside_score,expectation_gap_score,
                   early_discovery_score,price_maturity_score,
                   data_quality,stage,action,price_stage,source
            FROM snapshots
            WHERE ticker=? AND error IS NULL
            ORDER BY run_id DESC LIMIT ?
            """,
            (ticker.upper(), limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def latest_changes(self, limit: int = 25) -> list[dict[str, Any]]:
        run_id = self.latest_run_id()
        if run_id is None:
            return []
        rows = self.conn.execute(
            """
            SELECT * FROM snapshots
            WHERE run_id=? AND error IS NULL AND score_delta_last IS NOT NULL
            ORDER BY ABS(score_delta_last) DESC
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
