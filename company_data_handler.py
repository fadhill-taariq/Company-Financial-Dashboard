"""Gather everything the dashboard shows about one company.

This takes the place of covid_data_handler.py: the company stands in for the
local area, and a benchmark (the S&P 500 by default) stands in for the nation,
so the company's figures always have something to be compared against.

Live data is tried first. If the company's profile or quote can't be fetched
(no key, no network, quota used up), the bundled sample data is used instead
and labelled as such, the same way the COVID dashboard fell back to its snapshot.
"""

import logging
import re
from datetime import datetime

from providers import SAMPLE_LABEL, ProviderError, SampleProvider

SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,11}$")

EMPTY_METRICS = dict.fromkeys(
    ("market_cap", "pe", "eps", "beta", "week52_high", "week52_low",
     "dividend_yield", "return_5d", "return_ytd", "return_52w",
     "rel_sp500_52w", "net_margin", "revenue_growth"))


def normalise_symbol(text: str):
    """Return an upper-case ticker, or None if the text can't be one."""
    symbol = (text or "").strip().upper()
    return symbol if SYMBOL_PATTERN.match(symbol) else None


def _try(call, notes: list, what: str):
    """Run a provider call; on failure note why and return None."""
    try:
        return call()
    except ProviderError as error:
        logging.info("%s unavailable: %s", what, error)
        notes.append(f"{what} unavailable: {error}")
        return None


def _gather(symbol, market, history_provider, benchmark_symbol):
    """Fetch every section from the given providers. Raises if the core is missing."""
    notes = []
    profile = market.get_profile(symbol)  # these two are essential:
    quote = market.get_quote(symbol)      # let ProviderError propagate
    metrics = _try(lambda: market.get_metrics(symbol), notes, "Key metrics")
    history = (_try(lambda: history_provider.get_price_history(symbol), notes, "Price chart")
               if history_provider else None)
    benchmark_quote = _try(lambda: market.get_quote(benchmark_symbol), notes, "Benchmark")
    return profile, quote, metrics, history, benchmark_quote, notes


def get_company_data(symbol: str, providers: dict, benchmark_symbol: str = "SPY",
                     benchmark_name: str = "S&P 500 (SPY)",
                     sample: SampleProvider = None, now=datetime.now) -> dict:
    """Return the company's profile, quote, metrics, chart data and benchmark.

    The result always has the same keys. If nothing at all is available,
    'available' is False and 'message' says why.
    """
    sample = sample or SampleProvider()
    market = providers["market_data"]
    result = {
        "symbol": symbol,
        "available": False,
        "profile": {"symbol": symbol, "name": symbol},
        "quote": None,
        "metrics": dict(EMPTY_METRICS),
        "history": None,
        "benchmark": {"symbol": benchmark_symbol, "name": benchmark_name,
                      "change_pct": None},
        "source": "",
        "is_sample": False,
        "notes": [],
        "message": None,
        "updated": now(),
    }

    try:
        gathered = _gather(symbol, market, providers.get("price_history"), benchmark_symbol)
        result["source"] = market.label
        result["is_sample"] = market.name == "sample"
        logging.info("Fetched live data for %s from %s", symbol, market.label)
    except ProviderError as live_error:
        logging.warning("Live data for %s unavailable (%s); trying sample data",
                        symbol, live_error)
        try:
            gathered = _gather(symbol, sample, sample, benchmark_symbol)
        except ProviderError:
            result["message"] = (f"Couldn't load data for {symbol}: {live_error}. "
                                 f"Sample data is only bundled for "
                                 f"{', '.join(sample.available_symbols()) or 'no companies'}.")
            return result
        result["is_sample"] = True
        result["notes"].append(f"Live data unavailable: {live_error}")

    profile, quote, metrics, history, benchmark_quote, notes = gathered
    if result["is_sample"]:
        result["source"] = SAMPLE_LABEL
    result.update(
        available=True,
        profile=profile,
        quote=quote,
        metrics={**EMPTY_METRICS, **(metrics or {})},
        history=history or None,
    )
    result["notes"].extend(notes)
    if benchmark_quote:
        result["benchmark"]["change_pct"] = benchmark_quote.get("change_pct")
    return result
