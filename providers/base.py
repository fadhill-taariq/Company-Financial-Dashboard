"""The interface every data provider implements, plus shared helpers.

A provider turns one external API's responses into the dashboard's own
standard shapes, so the rest of the app never sees API-specific field names:

profile  {symbol, name, exchange, currency, country, industry, logo, website}
quote    {price, change, change_pct, high, low, open, prev_close}
metrics  {market_cap, pe, eps, beta, week52_high, week52_low, dividend_yield,
          return_5d, return_ytd, return_52w, rel_sp500_52w, net_margin,
          revenue_growth}
history  [{date: "YYYY-MM-DD", close: float}, ...] oldest first
article  {title, summary, url, source, published (datetime or None), image}
match    {symbol, name, type}

Percentages are stored as percent values (2.5 means 2.5%). Market cap is in
whole units of the company's currency. Any value a provider can't supply is
None, and the dashboard shows "Not available" for it.

A provider that doesn't support a method at all leaves the base version in
place, which raises NotSupported.
"""

import logging
import time


class ProviderError(Exception):
    """A provider could not return the data (no key, network error, quota...)."""


class NotSupported(ProviderError):
    """This provider doesn't offer that kind of data."""


class Provider:
    name = "base"
    label = "Base provider"

    def get_profile(self, symbol: str) -> dict:
        raise NotSupported(f"{self.label} does not provide company profiles")

    def get_quote(self, symbol: str) -> dict:
        raise NotSupported(f"{self.label} does not provide quotes")

    def get_metrics(self, symbol: str) -> dict:
        raise NotSupported(f"{self.label} does not provide key metrics")

    def get_price_history(self, symbol: str) -> list:
        raise NotSupported(f"{self.label} does not provide price history")

    def get_company_news(self, symbol: str, company_name: str = "",
                         limit: int = 3) -> list:
        raise NotSupported(f"{self.label} does not provide company news")

    def get_market_news(self, limit: int = 5) -> list:
        raise NotSupported(f"{self.label} does not provide market news")

    def search_symbols(self, query: str) -> list:
        raise NotSupported(f"{self.label} does not provide symbol search")


class CachedProvider(Provider):
    """Wraps a provider and remembers its answers for a while.

    Free API tiers are tight (Alpha Vantage allows 25 requests a day), so
    switching back to a company you looked at a few minutes ago reuses the
    earlier answer instead of spending another request. Errors aren't cached.
    """

    def __init__(self, inner: Provider, ttl_seconds: float = 600,
                 clock=time.monotonic):
        self.inner = inner
        self.name = inner.name
        self.label = inner.label
        self.ttl = ttl_seconds
        self._clock = clock
        self._store = {}

    def _cached(self, method: str, *args):
        key = (method,) + args
        hit = self._store.get(key)
        if hit and self._clock() - hit[0] < self.ttl:
            return hit[1]
        value = getattr(self.inner, method)(*args)
        self._store[key] = (self._clock(), value)
        return value

    def clear(self) -> None:
        self._store.clear()

    def get_profile(self, symbol):
        return self._cached("get_profile", symbol)

    def get_quote(self, symbol):
        return self._cached("get_quote", symbol)

    def get_metrics(self, symbol):
        return self._cached("get_metrics", symbol)

    def get_price_history(self, symbol):
        return self._cached("get_price_history", symbol)

    def get_company_news(self, symbol, company_name="", limit=3):
        return self._cached("get_company_news", symbol, company_name, limit)

    def get_market_news(self, limit=5):
        return self._cached("get_market_news", limit)

    def search_symbols(self, query):
        return self._cached("search_symbols", query)


def to_float(value):
    """Convert an API value to float, treating blanks, 'None' and '-' as missing."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip().rstrip("%").replace(",", "")
        if value in ("", "None", "-", "N/A", "null"):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_present(data: dict, *keys):
    """Return the first of several possible keys that holds a usable number."""
    for key in keys:
        value = to_float(data.get(key))
        if value is not None:
            return value
    return None


def request_json(session, url: str, params: dict, headers: dict = None,
                 label: str = "API") -> object:
    """GET a URL and return its JSON, raising ProviderError on any failure."""
    import requests  # imported here so tests with fake sessions don't need it

    http = session or requests
    try:
        response = http.get(url, params=params, headers=headers or {}, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        # requests' own messages include the full URL, and some APIs take the
        # key as a query parameter, so only the error type and status are logged
        status = getattr(getattr(error, "response", None), "status_code", None)
        logging.error("%s request to %s failed: %s%s", label, url,
                      type(error).__name__, f" (HTTP {status})" if status else "")
        raise ProviderError(f"{label} request failed") from error
