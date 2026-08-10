from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


def _extract_close(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close = raw["Close"].copy()
        elif "Close" in raw.columns.get_level_values(1):
            close = raw.xs("Close", axis=1, level=1).copy()
        else:
            return pd.DataFrame()
    else:
        if "Close" not in raw.columns:
            return pd.DataFrame()
        close = raw[["Close"]].copy()
        if len(tickers) == 1:
            close.columns = tickers

    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])

    close.columns = [str(c).upper() for c in close.columns]
    return close.sort_index()


def run_market_baseline(
    tickers: list[str],
    benchmark: str,
    start: str,
    top_k: int = 5,
    output_dir: str | Path = "outputs",
) -> tuple[pd.DataFrame, dict[str, float]]:
    symbols = sorted(set([t.upper() for t in tickers] + [benchmark.upper()]))
    raw = yf.download(
        symbols,
        start=start,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )
    close = _extract_close(raw, symbols).dropna(how="all")
    if close.empty or benchmark.upper() not in close.columns:
        raise RuntimeError("Could not download enough market data for the backtest.")

    monthly = close.resample("ME").last()
    returns_1m = monthly.pct_change()
    mom_3m = monthly.pct_change(3)
    mom_6m = monthly.pct_change(6)

    benchmark_col = benchmark.upper()
    universe_cols = [c for c in monthly.columns if c != benchmark_col]

    records: list[dict[str, float | str]] = []
    strategy_returns: list[float] = []
    benchmark_returns: list[float] = []

    # Signal at month t using information through t; hold through t+1.
    for i in range(6, len(monthly) - 1):
        date = monthly.index[i]
        next_date = monthly.index[i + 1]

        score = (0.4 * mom_3m.iloc[i] + 0.6 * mom_6m.iloc[i]).dropna()
        score = score[[c for c in universe_cols if c in score.index]].sort_values(ascending=False)
        picks = list(score.head(top_k).index)

        if not picks:
            continue

        next_ret = returns_1m.iloc[i + 1]
        valid = [p for p in picks if p in next_ret.index and pd.notna(next_ret[p])]
        if not valid:
            continue

        strat_ret = float(next_ret[valid].mean())
        bench_ret = float(next_ret.get(benchmark_col, np.nan))
        if not np.isfinite(bench_ret):
            continue

        strategy_returns.append(strat_ret)
        benchmark_returns.append(bench_ret)
        records.append(
            {
                "signal_date": date.date().isoformat(),
                "holding_end": next_date.date().isoformat(),
                "picks": ",".join(valid),
                "strategy_return": strat_ret,
                "benchmark_return": bench_ret,
            }
        )

    if not records:
        raise RuntimeError("Backtest produced no valid monthly observations.")

    df = pd.DataFrame(records)
    df["strategy_equity"] = (1 + df["strategy_return"]).cumprod()
    df["benchmark_equity"] = (1 + df["benchmark_return"]).cumprod()

    n_years = max(len(df) / 12.0, 1 / 12)
    strat_total = float(df["strategy_equity"].iloc[-1] - 1)
    bench_total = float(df["benchmark_equity"].iloc[-1] - 1)
    strat_cagr = float(df["strategy_equity"].iloc[-1] ** (1 / n_years) - 1)
    bench_cagr = float(df["benchmark_equity"].iloc[-1] ** (1 / n_years) - 1)

    strat_vol = float(df["strategy_return"].std(ddof=1) * np.sqrt(12))
    strat_sharpe = (
        float(df["strategy_return"].mean() / df["strategy_return"].std(ddof=1) * np.sqrt(12))
        if df["strategy_return"].std(ddof=1) > 0
        else float("nan")
    )

    equity = df["strategy_equity"]
    max_dd = float((equity / equity.cummax() - 1).min())

    metrics = {
        "months": float(len(df)),
        "strategy_total_return": strat_total,
        "benchmark_total_return": bench_total,
        "strategy_cagr": strat_cagr,
        "benchmark_cagr": bench_cagr,
        "strategy_annualized_volatility": strat_vol,
        "strategy_sharpe_zero_rf": strat_sharpe,
        "strategy_max_drawdown": max_dd,
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "market_baseline_backtest.csv", index=False)
    return df, metrics
