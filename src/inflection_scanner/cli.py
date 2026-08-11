from __future__ import annotations

import json
from typing import Optional

import typer
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import load_settings, load_universe
from .db import Database
from .discovery_pipeline import run_discovery
from .full_research_pipeline import run_full_research
from .pipeline import run_scan
from .warehouse import ResearchWarehouse


app = typer.Typer(
    help="Large-Cap Inflection Research v5: persistent discovery, trust checks, valuation triangulation, and buy-zone decisions.",
    no_args_is_help=True,
)
console = Console()


def _pct(value):
    try:
        return f"{float(value):.1%}"
    except Exception:
        return "-"


def _money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "-"


def _num(value):
    try:
        return f"{float(value):.1f}"
    except Exception:
        return "-"


def _market_cap(value):
    try:
        return f"${float(value) / 1_000_000_000:.1f}B"
    except Exception:
        return "-"


def _progress(*args):
    if not args:
        return
    label = args[0]
    if label in {"initial", "incremental"}:
        _, current, total, rows = args
        if current == 1 or current == total or current % 5 == 0:
            print(f"Market {label}: batch {current}/{total}; {rows:,} rows written to persistent cache")
    elif label == "features":
        _, current, total, usable = args
        print(f"Price features: {current}/{total}; usable={usable}")
    elif label == "deep":
        _, current, total, ticker = args
        print(f"Deep data {current}/{total}: {ticker}")
    elif label == "research":
        _, current, total, ticker = args
        print(f"Full research {current}/{total}: {ticker}")


@app.command()
def doctor(network: bool = typer.Option(False, "--network")):
    settings = load_settings()
    checks = [("config", settings.config_path.exists(), str(settings.config_path))]

    try:
        warehouse = ResearchWarehouse(settings.warehouse_path)
        info = warehouse.cache_info()
        warehouse.close()
        checks.append(("warehouse", True, f"{settings.warehouse_path} ({info['size_mb']} MB)"))
    except Exception as exc:
        checks.append(("warehouse", False, str(exc)))

    try:
        db = Database(settings.db_path)
        db.close()
        checks.append(("scanner db", True, str(settings.db_path)))
    except Exception as exc:
        checks.append(("scanner db", False, str(exc)))

    try:
        import yfinance as yf
        checks.append(("yfinance", True, getattr(yf, "__version__", "unknown")))
        if network:
            hist = yf.Ticker("AAPL").history(period="5d", auto_adjust=True)
            checks.append(("Yahoo network", not hist.empty, f"{len(hist)} rows"))
    except Exception as exc:
        checks.append(("Yahoo/yfinance", False, str(exc)))

    if network:
        try:
            from .providers.universe import fetch_us_listed_equities
            universe = fetch_us_listed_equities(settings.warehouse_path.parent / "cache", refresh=True)
            checks.append(("US listed universe", len(universe) > 1000, f"{len(universe)} symbols"))
        except Exception as exc:
            checks.append(("US listed universe", False, str(exc)))

    table = Table(title="V5 research engine doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for name, ok, detail in checks:
        table.add_row(name, "[green]OK[/green]" if ok else "[red]FAIL[/red]", detail)
    console.print(table)
    if not all(x[1] for x in checks):
        raise typer.Exit(1)


@app.command("cache-status")
def cache_status():
    settings = load_settings()
    warehouse = ResearchWarehouse(settings.warehouse_path)
    info = warehouse.cache_info()
    market = warehouse.get_fetch_state("market:all")
    warehouse.close()
    table = Table(title="Persistent research warehouse")
    table.add_column("Metric")
    table.add_column("Value")
    for key, value in info.items():
        table.add_row(key, str(value))
    table.add_row("last_market_refresh", str(market.get("fetched_at")) if market else "never")
    console.print(table)


@app.command()
def research(
    deep: int = typer.Option(180, min=60, max=500),
    research_count: int = typer.Option(20, "--research-count", min=5, max=75),
    top: int = typer.Option(30, min=5, max=100),
    max_universe: int = typer.Option(0, min=0),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    offline: bool = typer.Option(False, "--offline"),
):
    settings = load_settings()
    print(
        "[bold]Large-Cap Inflection Research v5[/bold]\n"
        "1. Broad U.S.-listed price discovery\n"
        "2. Large/high-liquidity challenger sleeve so established names are not missed\n"
        "3. Deep profiles, fundamentals, revisions, filings, and cached news\n"
        "4. Default full-research universe: established $15B+ CORE companies\n"
        "5. Multi-model valuation + data sanity checks\n"
        "6. Six-pillar conviction model\n"
        "7. BUY NOW / BUY ON PULLBACK / WATCH / TOO LATE / REVIEW DATA / PASS\n"
        "8. Persistent realized-outcome track record"
    )

    reports, meta = run_full_research(
        settings=settings,
        deep_candidates=deep,
        research_candidates=research_count,
        top_n=top,
        max_universe=max_universe or None,
        force_refresh=force_refresh,
        offline=offline,
        progress_callback=_progress,
    )

    order = {
        "BUY NOW": 0,
        "BUY ON PULLBACK": 1,
        "WATCH": 2,
        "TOO LATE": 3,
        "REVIEW DATA": 4,
        "SPECULATIVE WATCH": 5,
        "PASS": 6,
    }
    reports.sort(
        key=lambda r: (
            order.get(r.get("conviction", {}).get("action", "WATCH"), 9),
            -(r.get("conviction", {}).get("conviction_score") or -999),
        )
    )

    table = Table(title="V5 decision table")
    columns = [
        ("#", "right"), ("Ticker", None), ("Action", None), ("Conv", "right"), ("Tier", None),
        ("MktCap", "right"), ("Years", "right"), ("Analysts", "right"), ("Current", "right"),
        ("Buy<=", "right"), ("Base FV", "right"), ("Base CAGR", "right"), ("Bear", "right"),
        ("Models", "right"), ("Agree", "right"), ("Stage", None),
    ]
    for name, justify in columns:
        table.add_column(name, justify=justify)

    for i, r in enumerate(reports, 1):
        c = r.get("conviction", {})
        v = r.get("valuation", {})
        t = r.get("trust", {})
        m = r.get("metrics", {})
        table.add_row(
            str(i), r.get("ticker"), str(c.get("action")), _num(c.get("conviction_score")),
            str(t.get("risk_tier")), _market_cap(t.get("market_cap")), _num(t.get("years_public")),
            str(t.get("analyst_count") if t.get("analyst_count") is not None else "-"),
            _money(m.get("price")), _money(c.get("buy_below_price")), _money(c.get("base_fair_value")),
            _pct(v.get("base_cagr")), _pct(v.get("bear_return")), str(v.get("model_count")),
            _num(v.get("model_agreement")), str(r.get("discovery", {}).get("price_stage") or ""),
        )
    console.print(table)

    selection = meta.get("research_selection", {})
    print(
        "\nSelection: "
        f"CORE={selection.get('core_candidates', 0)}; "
        f"preferred $25B+={selection.get('preferred_large_cap_candidates', 0)}; "
        f"MIDCAP={selection.get('midcap_candidates', 0)}; "
        f"selected={selection.get('selected_for_research', 0)}."
    )
    print(f"Track-record matured observations: {meta.get('track_record_observations', 0)}")
    print("\nPublished dashboard files:")
    for name, path in meta.get("published", {}).items():
        print(f"  {name}: {path}")


@app.command()
def discover(
    deep: int = typer.Option(180, min=60, max=500),
    top: int = typer.Option(30, min=5, max=100),
    max_universe: int = typer.Option(0, min=0),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    offline: bool = typer.Option(False, "--offline"),
):
    settings = load_settings()
    snapshots, _ = run_discovery(
        settings=settings,
        deep_candidates=deep,
        top_n=top,
        max_universe=max_universe or None,
        force_refresh=force_refresh,
        offline=offline,
        progress_callback=_progress,
    )
    ok = sorted(
        [x for x in snapshots if not x.get("error")],
        key=lambda x: x.get("scores", {}).get("total", -1),
        reverse=True,
    )
    table = Table(title="Discovery candidates before large-cap research gate")
    for name in ["Ticker", "Potential", "Stage", "Bucket", "12M", "DollarVol"]:
        table.add_column(name)
    for item in ok[:top]:
        f = item.get("features", {})
        table.add_row(
            item.get("ticker"), _num(item.get("scores", {}).get("total")),
            str(item.get("assessment", {}).get("price_stage") or ""),
            str(f.get("discovery_bucket") or ""), _pct(f.get("return_12m")), _market_cap(f.get("dollar_volume_20d")),
        )
    console.print(table)


@app.command()
def explain(ticker: str):
    settings = load_settings()
    warehouse = ResearchWarehouse(settings.warehouse_path)
    report = warehouse.latest_research_report(ticker)
    warehouse.close()
    if not report:
        print(f"[yellow]No report for {ticker.upper()}. Run `inflection-scanner research` first.[/yellow]")
        raise typer.Exit(1)

    c = report.get("conviction", {})
    v = report.get("valuation", {})
    t = report.get("trust", {})
    m = report.get("metrics", {})
    console.print(
        Panel(
            f"[bold]{ticker.upper()} — {report.get('company')}[/bold]\n"
            f"Action: [bold]{c.get('action')}[/bold] | Conviction: {c.get('conviction_score')} | "
            f"Tier: {t.get('risk_tier')} / {t.get('size_class')} | Market cap: {_market_cap(t.get('market_cap'))} | "
            f"Years public: {_num(t.get('years_public'))} | Analysts: {t.get('analyst_count')}\n"
            f"Current: {_money(m.get('price'))} | Buy below: {_money(c.get('buy_below_price'))} | "
            f"Base fair: {_money(c.get('base_fair_value'))} | Base CAGR: {_pct(v.get('base_cagr'))} | Bear: {_pct(v.get('bear_return'))}",
            title="V5 investment decision",
        )
    )
    pillar_table = Table(title="Conviction pillars")
    pillar_table.add_column("Pillar")
    pillar_table.add_column("Score", justify="right")
    for k, value in c.get("pillars", {}).items():
        pillar_table.add_row(k, _num(value))
    console.print(pillar_table)

    for title, key in [
        ("Evidence supporting the case", "why_buy"),
        ("Reasons not to buy", "why_not"),
        ("What must be true", "what_must_be_true"),
        ("Thesis invalidation", "invalidation"),
    ]:
        print(f"\n[bold]{title}[/bold]")
        for item in report.get(key, []):
            print(f" • {item}")


@app.command()
def scan(
    universe: str = typer.Option("config/watchlist.json"),
    tickers: Optional[str] = typer.Option(None),
    top: int = typer.Option(20),
):
    settings = load_settings()
    items = load_universe(universe)
    if tickers:
        items = [{"ticker": x.strip().upper(), "themes": []} for x in tickers.split(",") if x.strip()]
    snapshots, _ = run_scan(items, settings, top_n=top)
    print(f"Manual scan complete: {len(snapshots)} names.")


if __name__ == "__main__":
    app()
