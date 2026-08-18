from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import MODEL_VERSION, __version__
from .config import load_config, load_security_overrides
from .discovery_pipeline import run_discovery
from .full_research_pipeline import run_full_research
from .providers.sec import valid_user_agent
from .providers.universe import normalize_tickers
from .providers.yahoo import YahooProvider
from .warehouse import ResearchWarehouse

app=typer.Typer(no_args_is_help=True,help="Large-cap inflection/bottleneck research engine.")
console=Console()

@app.command()
def version():
    console.print(f"inflection-bottleneck-scanner {__version__} / model {MODEL_VERSION}")

@app.command()
def doctor(network: bool = typer.Option(False,"--network",help="Also test Yahoo/SEC availability.")):
    cfg=load_config(); checks={"config":"OK","model_version":cfg.get("model_version"),"sec_user_agent":"configured" if valid_user_agent(os.getenv("SEC_USER_AGENT")) else "optional/unconfigured"}
    if network:
        p=YahooProvider(pause_seconds=0,retries=0)
        try:
            df=p.history("SPY","5d"); checks["yahoo"]="OK" if not df.empty else "NO DATA"
        except Exception as exc: checks["yahoo"]=f"ERROR:{exc.__class__.__name__}"
    console.print_json(json.dumps(checks))

@app.command("cache-status")
def cache_status(warehouse_path: str="data/warehouse.db"):
    w=ResearchWarehouse(warehouse_path)
    try: console.print_json(json.dumps(w.stats()))
    finally: w.close()

@app.command()
def research(
    deep: int = typer.Option(180,"--deep"),
    research_count: int = typer.Option(24,"--research-count"),
    top: int = typer.Option(30,"--top"),
    force_refresh: bool = typer.Option(False,"--force-refresh"),
    tickers: str | None = typer.Option(None,"--tickers",help="Comma-separated universe override."),
    config_path: str="config/default.json",
    warehouse_path: str="data/warehouse.db",
    published: str="published",
):
    cfg=load_config(config_path); overrides=load_security_overrides(); w=ResearchWarehouse(warehouse_path); p=YahooProvider(float(cfg.get("request_pause_seconds",.08)))
    universe=normalize_tickers(tickers.split(",")) if tickers else None
    try:
        discovery=run_discovery(p,w,cfg,universe,deep,force_refresh)
        result=run_full_research(p,w,cfg,discovery,overrides,research_count,published,force_refresh)
    finally: w.close()
    table=Table(title=f"V{MODEL_VERSION} Research")
    for col in ["Ticker","Action","Thesis","Entry","Valuation","Price","Buy below"]: table.add_column(col)
    for r in result["reports"][:top]:
        c=r.get("conviction",{}); v=r.get("valuation",{}); m=r.get("metrics",{})
        table.add_row(str(r.get("ticker")),str(c.get("action")),str(c.get("thesis_score")),str(c.get("entry_score")),str(v.get("valuation_status")),str(m.get("price")),str(c.get("buy_below_price")))
    console.print(table)
    console.print(f"Published {len(result['reports'])} reports to {published}")

@app.command()
def validate(published: str="published"):
    p=Path(published)/"latest_research.json"
    if not p.exists(): raise typer.Exit(code=2)
    rows=json.loads(p.read_text()); console.print(f"OK: {len(rows)} reports")
