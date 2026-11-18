"""Offline sample data, used when no live provider can answer.

Files live in data/sample/<SYMBOL>.json. The figures are illustrative, not
real market data, and the dashboard labels them that way whenever they're shown.
"""

import json
import os

from config import BASE_DIR

from .base import Provider, ProviderError

SAMPLE_DIR = os.path.join(BASE_DIR, "data", "sample")
SAMPLE_LABEL = "Sample data (illustrative figures, not real market data)"


class SampleProvider(Provider):
    name = "sample"
    label = "Sample data"

    def __init__(self, directory: str = SAMPLE_DIR):
        self.directory = directory

    def available_symbols(self) -> list:
        try:
            return sorted(f[:-5] for f in os.listdir(self.directory) if f.endswith(".json"))
        except OSError:
            return []

    def _load(self, symbol: str) -> dict:
        path = os.path.join(self.directory, f"{symbol.upper()}.json")
        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise ProviderError(f"No sample data for {symbol}") from error

    def _section(self, symbol, section):
        data = self._load(symbol).get(section)
        if data is None:
            raise ProviderError(f"Sample data for {symbol} has no {section}")
        return data

    def get_profile(self, symbol):
        return self._section(symbol, "profile")

    def get_quote(self, symbol):
        return self._section(symbol, "quote")

    def get_metrics(self, symbol):
        return self._section(symbol, "metrics")

    def get_price_history(self, symbol):
        return self._section(symbol, "history")

    def search_symbols(self, query):
        query = query.lower()
        matches = []
        for symbol in self.available_symbols():
            profile = self._load(symbol).get("profile")
            if profile and (query in symbol.lower() or query in profile["name"].lower()):
                matches.append({"symbol": symbol, "name": profile["name"],
                                "type": "Sample data"})
        return matches
