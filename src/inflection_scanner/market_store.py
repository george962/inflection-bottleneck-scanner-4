from __future__ import annotations

from .warehouse import ResearchWarehouse


class MarketStore:
    def __init__(self, warehouse: ResearchWarehouse): self.warehouse=warehouse
    def get(self,ticker): return self.warehouse.price_history(ticker)
    def put(self,ticker,df): return self.warehouse.upsert_prices(ticker,df)
