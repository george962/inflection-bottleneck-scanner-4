from __future__ import annotations
import json
from typing import Optional
import typer
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from .config import load_settings,load_universe
from .db import Database
from .discovery_pipeline import run_discovery
from .full_research_pipeline import run_full_research
from .pipeline import run_scan
from .warehouse import ResearchWarehouse

app=typer.Typer(help="Persistent Stock Discovery + Automated Equity Research Engine",no_args_is_help=True)
console=Console()
def _pct(v):
    try:return f"{float(v):.1%}"
    except Exception:return "-"
def _money(v):
    try:return f"${float(v):,.2f}"
    except Exception:return "-"
def _num(v):
    try:return f"{float(v):.1f}"
    except Exception:return "-"
def _progress(*args):
    if not args:return
    label=args[0]
    if label in {"initial","incremental"}:
        _,cur,total,rows=args
        if cur==1 or cur==total or cur%5==0:print(f"Market {label}: batch {cur}/{total}; {rows:,} rows written to persistent cache")
    elif label=="features":
        _,cur,total,usable=args;print(f"Price features: {cur}/{total}; usable={usable}")
    elif label=="deep":
        _,cur,total,t=args;print(f"Deep data {cur}/{total}: {t}")
    elif label=="research":
        _,cur,total,t=args;print(f"Automated research {cur}/{total}: {t}")

@app.command()
def doctor(network:bool=typer.Option(False,"--network")):
    s=load_settings();checks=[("config",s.config_path.exists(),str(s.config_path))]
    try:
        w=ResearchWarehouse(s.warehouse_path);i=w.cache_info();w.close();checks.append(("warehouse",True,f"{s.warehouse_path} ({i['size_mb']} MB)"))
    except Exception as e:checks.append(("warehouse",False,str(e)))
    try:
        d=Database(s.db_path);d.close();checks.append(("scanner db",True,str(s.db_path)))
    except Exception as e:checks.append(("scanner db",False,str(e)))
    try:
        import yfinance as yf
        checks.append(("yfinance",True,getattr(yf,"__version__","unknown")))
        if network:
            h=yf.Ticker("AAPL").history(period="5d",auto_adjust=True);checks.append(("Yahoo network",not h.empty,f"{len(h)} rows"))
    except Exception as e:checks.append(("Yahoo/yfinance",False,str(e)))
    if network:
        try:
            from .providers.universe import fetch_us_listed_equities
            u=fetch_us_listed_equities(s.warehouse_path.parent/"cache",refresh=True);checks.append(("US listed universe",len(u)>1000,f"{len(u)} symbols"))
        except Exception as e:checks.append(("US listed universe",False,str(e)))
    t=Table(title="Research engine doctor");t.add_column("Check");t.add_column("Status");t.add_column("Detail")
    for n,ok,d in checks:t.add_row(n,"[green]OK[/green]" if ok else "[red]FAIL[/red]",d)
    console.print(t)
    if not all(x[1] for x in checks):raise typer.Exit(1)

@app.command("cache-status")
def cache_status():
    s=load_settings();w=ResearchWarehouse(s.warehouse_path);i=w.cache_info();m=w.get_fetch_state("market:all");w.close()
    t=Table(title="Persistent research warehouse");t.add_column("Metric");t.add_column("Value")
    for k,v in i.items():t.add_row(k,str(v))
    t.add_row("last_market_refresh",str(m.get("fetched_at")) if m else "never");console.print(t)

@app.command()
def research(deep:int=typer.Option(100,min=20,max=300),research_count:int=typer.Option(20,"--research-count",min=5,max=60),
             top:int=typer.Option(30,min=5,max=100),max_universe:int=typer.Option(0,min=0),
             force_refresh:bool=typer.Option(False,"--force-refresh"),offline:bool=typer.Option(False,"--offline")):
    s=load_settings()
    print("[bold]Full automated equity-research pipeline[/bold]\n1. Persistent prices\n2. Broad discovery\n3. Cached fundamentals/revisions\n4. Cached filings/news\n5. Bear/base/bull valuation\n6. BUY / SMALL BUY / WATCH / TOO LATE / PASS")
    reports,meta=run_full_research(s,deep,research_count,top,max_universe=max_universe or None,force_refresh=force_refresh,offline=offline,progress_callback=_progress)
    order={"BUY":0,"SMALL BUY / SPECULATIVE":1,"WATCH":2,"TOO LATE":3,"PASS":4}
    reports.sort(key=lambda r:(order.get(r.get("decision",{}).get("decision","WATCH"),5),-(r.get("valuation",{}).get("expected_cagr") or -999)))
    t=Table(title="Automated investment research");t.add_column("#",justify="right");t.add_column("Ticker");t.add_column("Decision");t.add_column("Conf.")
    t.add_column("Current",justify="right");t.add_column("Expected 3Y",justify="right");t.add_column("Exp CAGR",justify="right")
    t.add_column("P(profit)",justify="right");t.add_column("Bear",justify="right");t.add_column("Stage");t.add_column("Type")
    for i,r in enumerate(reports,1):
        v=r.get("valuation",{});d=r.get("decision",{});m=r.get("metrics",{})
        t.add_row(str(i),r["ticker"],str(d.get("decision")),str(d.get("confidence")),_money(m.get("price")),_money(v.get("expected_value")),
                  _pct(v.get("expected_cagr")),_pct(v.get("probability_profit")),_pct(v.get("bear_downside")),
                  str(r.get("discovery",{}).get("price_stage") or ""),str(v.get("company_type") or ""))
    console.print(t)
    wh=meta.get("warehouse_after_research",{})
    print(f"\nPersistent warehouse: {wh.get('price_rows',0):,} price rows, {wh.get('json_cache_entries',0)} cached deep objects, {wh.get('filing_documents',0)} SEC documents.")
    print("\nPublished dashboard files:")
    for n,p in meta.get("published",{}).items():print(f"  {n}: {p}")

@app.command()
def discover(deep:int=typer.Option(100,min=20,max=300),top:int=typer.Option(30,min=5,max=100),max_universe:int=typer.Option(0,min=0),
             force_refresh:bool=typer.Option(False,"--force-refresh"),offline:bool=typer.Option(False,"--offline")):
    s=load_settings();snaps,_=run_discovery(s,deep,top,max_universe=max_universe or None,force_refresh=force_refresh,offline=offline,progress_callback=_progress)
    ok=sorted([x for x in snaps if not x.get("error")],key=lambda x:x.get("scores",{}).get("total",-1),reverse=True)
    t=Table(title="Discovery candidates");t.add_column("Ticker");t.add_column("Potential");t.add_column("Stage");t.add_column("Bucket");t.add_column("12M")
    for x in ok[:top]:
        f=x.get("features",{});sc=x.get("scores",{});a=x.get("assessment",{})
        t.add_row(x["ticker"],_num(sc.get("total")),str(a.get("price_stage") or ""),str(f.get("discovery_bucket") or ""),_pct(f.get("return_12m")))
    console.print(t)

@app.command()
def explain(ticker:str):
    s=load_settings();w=ResearchWarehouse(s.warehouse_path);r=w.latest_research_report(ticker);w.close()
    if not r:
        print(f"[yellow]No research report for {ticker.upper()}. Run `inflection-scanner research` first.[/yellow]");raise typer.Exit(1)
    v=r.get("valuation",{});d=r.get("decision",{});m=r.get("metrics",{})
    console.print(Panel(f"[bold]{ticker.upper()} — {r.get('company')}[/bold]\nDecision: [bold]{d.get('decision')}[/bold] | Confidence: {d.get('confidence')} | Current: {_money(m.get('price'))} | Expected {v.get('horizon_years',3)}Y value: {_money(v.get('expected_value'))} | Expected CAGR: {_pct(v.get('expected_cagr'))} | P(profit): {_pct(v.get('probability_profit'))} | Bear downside: {_pct(v.get('bear_downside'))}",title="Automated investment decision"))
    t=Table(title=f"Valuation model: {v.get('model')}");t.add_column("Scenario");t.add_column("Probability");t.add_column("Fair value");t.add_column("Assumptions")
    for sc in v.get("scenarios",[]):t.add_row(str(sc.get("name")),_pct(sc.get("probability")),_money(sc.get("fair_value")),json.dumps(sc.get("assumptions",{})))
    console.print(t)
    for title,key in [("Why buy","why_buy"),("Why NOT to buy","why_not"),("What would change the decision","what_changes_decision")]:
        print(f"\n[bold]{title}[/bold]")
        for item in r.get(key,[]):print(f" • {item}")
    if r.get("filing_evidence"):
        print("\n[bold]SEC filing evidence[/bold]")
        for e in r["filing_evidence"][:10]:print(f" • [{e.get('form')} {e.get('filing_date')}] {e.get('topic')}/{e.get('tone')}: {e.get('text')}")
    if r.get("llm_research_note"):print("\n[bold]Optional AI evidence synthesis[/bold]\n"+r["llm_research_note"])

@app.command()
def scan(universe:str=typer.Option("config/watchlist.json"),tickers:Optional[str]=typer.Option(None),top:int=typer.Option(20)):
    s=load_settings();items=load_universe(universe)
    if tickers:items=[{"ticker":x.strip().upper(),"themes":[]} for x in tickers.split(",") if x.strip()]
    snaps,_=run_scan(items,s,top_n=top);print(f"Manual scan complete: {len(snaps)} names.")

if __name__=="__main__":app()
