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
    help="Persistent Stock Discovery + Trust-Gated Automated Equity Research Engine",
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
            print(f"Market {label}: batch {current}/{total}; {rows:,} rows written to cache")
    elif label == "features":
        _, current, total, usable = args
        print(f"Price features: {current}/{total}; usable={usable}")
    elif label == "deep":
        _, current, total, ticker = args
        print(f"Deep data {current}/{total}: {ticker}")
    elif label == "research":
        _, current, total, ticker = args
        print(f"Automated research {current}/{total}: {ticker}")


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

    table = Table(title="Research engine doctor")
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
    deep: int = typer.Option(160, min=40, max=400),
    research_count: int = typer.Option(20, "--research-count", min=5, max=60),
    top: int = typer.Option(30, min=5, max=100),
    max_universe: int = typer.Option(0, min=0),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    offline: bool = typer.Option(False, "--offline"),
):
    settings = load_settings()
    print(
        "[bold]Trust-gated equity research[/bold]\n"
        "1. Persistent prices\n"
        "2. Broad discovery + high-liquidity challengers\n"
        "3. Prefer established $10B+ CORE companies\n"
        "4. Cached fundamentals/revisions + SEC evidence\n"
        "5. Multiple valuation methods\n"
        "6. Data sanity/trust gate\n"
        "7. BUY / WATCH / TOO LATE / REVIEW DATA / PASS"
    )
    reports, meta = run_full_research(
        settings,
        deep,
        research_count,
        top,
        max_universe=max_universe or None,
        force_refresh=force_refresh,
        offline=offline,
        progress_callback=_progress,
    )

    order = {
        "BUY": 0,
        "SMALL BUY / SPECULATIVE": 1,
        "WATCH": 2,
        "TOO LATE": 3,
        "REVIEW DATA": 4,
        "SPECULATIVE WATCH": 5,
        "PASS": 6,
    }
    reports.sort(
        key=lambda report: (
            order.get(report.get("decision", {}).get("decision", "WATCH"), 9),
            -(report.get("valuation", {}).get("expected_cagr") or -999),
        )
    )

    table = Table(title="Trust-gated investment research")
    for name, justify in [
        ("#", "right"),
        ("Ticker", None),
        ("Decision", None),
        ("Trust", None),
        ("Tier", None),
        ("MktCap", "right"),
        ("Years", "right"),
        ("Analysts", "right"),
        ("Current", "right"),
        ("Base FV", "right"),
        ("Exp CAGR", "right"),
        ("Bear", "right"),
        ("Models", "right"),
        ("Agree", "right"),
        ("Stage", None),
    ]:
        table.add_column(name, justify=justify)

    for i, report in enumerate(reports, 1):
        valuation = report.get("valuation", {})
        decision = report.get("decision", {})
        metrics = report.get("metrics", {})
        trust = report.get("trust", {})
        scenarios = {x.get("name"): x for x in valuation.get("scenarios", [])}
        table.add_row(
            str(i),
            report["ticker"],
            str(decision.get("decision")),
            f"{trust.get('trust_grade')}/{trust.get('trust_score')}",
            str(trust.get("risk_tier")),
            _market_cap(trust.get("market_cap")),
            _num(trust.get("years_public")),
            str(trust.get("analyst_count") if trust.get("analyst_count") is not None else "-"),
            _money(metrics.get("price")),
            _money(scenarios.get("Base", {}).get("fair_value")),
            _pct(valuation.get("expected_cagr")),
            _pct(valuation.get("bear_return")),
            str(valuation.get("model_count")),
            _num(valuation.get("model_agreement")),
            str(report.get("discovery", {}).get("price_stage") or ""),
        )
    console.print(table)

    selection = meta.get("research_selection", {})
    print(
        "\nResearch selection: "
        f"CORE={selection.get('core_candidates', 0)}, "
        f"MIDCAP={selection.get('midcap_candidates', 0)}, "
        f"SPECULATIVE={selection.get('speculative_candidates', 0)}, "
        f"selected={selection.get('selected_for_research', 0)}."
    )
    print("\nNote: scenario weights are NOT calibrated probabilities. Extreme upside is automatically changed to REVIEW DATA.")
    print("\nPublished dashboard files:")
    for name, path in meta.get("published", {}).items():
        print(f"  {name}: {path}")


@app.command()
def discover(
    deep: int = typer.Option(160, min=40, max=400),
    top: int = typer.Option(30, min=5, max=100),
    max_universe: int = typer.Option(0, min=0),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    offline: bool = typer.Option(False, "--offline"),
):
    settings = load_settings()
    snapshots, _ = run_discovery(
        settings,
        deep,
        top,
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
    table = Table(title="Discovery candidates")
    table.add_column("Ticker")
    table.add_column("Potential")
    table.add_column("Stage")
    table.add_column("Bucket")
    table.add_column("12M")
    for item in ok[:top]:
        features = item.get("features", {})
        scores = item.get("scores", {})
        assessment = item.get("assessment", {})
        table.add_row(
            item["ticker"],
            _num(scores.get("total")),
            str(assessment.get("price_stage") or ""),
            str(features.get("discovery_bucket") or ""),
            _pct(features.get("return_12m")),
        )
    console.print(table)


@app.command()
def explain(ticker: str):
    settings = load_settings()
    warehouse = ResearchWarehouse(settings.warehouse_path)
    report = warehouse.latest_research_report(ticker)
    warehouse.close()
    if not report:
        print(f"[yellow]No research report for {ticker.upper()}. Run `inflection-scanner research` first.[/yellow]")
        raise typer.Exit(1)

    valuation = report.get("valuation", {})
    decision = report.get("decision", {})
    metrics = report.get("metrics", {})
    trust = report.get("trust", {})
    scenarios = {x.get("name"): x for x in valuation.get("scenarios", [])}

    console.print(
        Panel(
            f"[bold]{ticker.upper()} — {report.get('company')}[/bold]\n"
            f"Decision: [bold]{decision.get('decision')}[/bold] | "
            f"Trust: {trust.get('trust_grade')}/{trust.get('trust_score')} | "
            f"Tier: {trust.get('risk_tier')} | "
            f"Market cap: {_market_cap(trust.get('market_cap'))} | "
            f"Years public: {_num(trust.get('years_public'))} | "
            f"Analysts: {trust.get('analyst_count')} | "
            f"Current: {_money(metrics.get('price'))} | "
            f"Base fair value: {_money(scenarios.get('Base', {}).get('fair_value'))} | "
            f"Expected CAGR: {_pct(valuation.get('expected_cagr'))} | "
            f"Bear return: {_pct(valuation.get('bear_return'))}",
            title="Trust-gated investment decision",
        )
    )

    table = Table(title=f"Valuation methods: {valuation.get('model_count')} | agreement={valuation.get('model_agreement')}")
    table.add_column("Scenario")
    table.add_column("Weight")
    table.add_column("Fair value")
    table.add_column("Model values")
    for scenario in valuation.get("scenarios", []):
        table.add_row(
            str(scenario.get("name")),
            _pct(scenario.get("weight")),
            _money(scenario.get("fair_value")),
            json.dumps(scenario.get("model_values", [])),
        )
    console.print(table)

    if trust.get("critical_flags"):
        print("\n[bold red]CRITICAL DATA/VALUATION FLAGS[/bold red]")
        for item in trust.get("critical_flags", []):
            print(f" • {item}")

    for title, key in [
        ("Why buy", "why_buy"),
        ("Why NOT to buy", "why_not"),
        ("What would change the decision", "what_changes_decision"),
    ]:
        print(f"\n[bold]{title}[/bold]")
        for item in report.get(key, []):
            print(f" • {item}")

    print("\n[bold]Data trust checks[/bold]")
    for check in trust.get("checks", []):
        print(f" • {check.get('status')} — {check.get('check')}: {check.get('detail')}")


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
