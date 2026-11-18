"""Fake HTTP sessions and providers so tests never touch the network."""

from providers import Provider, ProviderError


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} Error", response=self)

    def json(self):
        return self._payload


class FakeSession:
    """Returns a payload chosen by URL path (and optionally a query parameter)."""

    def __init__(self, routes, status=200):
        self.routes = routes
        self.status = status
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        for key, payload in self.routes.items():
            if callable(key):
                if key(url, params or {}):
                    return FakeResponse(payload, self.status)
            elif url.endswith(key):
                return FakeResponse(payload, self.status)
        return FakeResponse({}, self.status)


class FailingProvider(Provider):
    """A live provider that is always unavailable, e.g. no key configured."""
    name = "failing"
    label = "Failing provider"

    def _fail(self, *args, **kwargs):
        raise ProviderError("No API key configured")

    get_profile = get_quote = get_metrics = get_price_history = _fail
    get_company_news = get_market_news = search_symbols = _fail


class FakeMarket(Provider):
    """A live provider with fixed data for a couple of companies."""
    name = "fake"
    label = "Fake market data"

    COMPANIES = {
        "AAPL": {"name": "Apple Inc", "price": 230.0, "change_pct": -1.25},
        "MSFT": {"name": "Microsoft Corp", "price": 410.0, "change_pct": 0.5},
        "SPY": {"name": "SPDR S&P 500", "price": 600.0, "change_pct": 0.25},
    }

    def __init__(self):
        self.calls = []

    def _company(self, symbol):
        self.calls.append(symbol)
        if symbol not in self.COMPANIES:
            raise ProviderError(f"Unknown symbol {symbol}")
        return self.COMPANIES[symbol]

    def get_profile(self, symbol):
        c = self._company(symbol)
        return {"symbol": symbol, "name": c["name"], "exchange": "NASDAQ",
                "currency": "USD", "country": "US", "industry": "Technology",
                "logo": None, "website": None}

    def get_quote(self, symbol):
        c = self._company(symbol)
        return {"price": c["price"], "change": None, "change_pct": c["change_pct"],
                "high": None, "low": None, "open": None, "prev_close": None}

    def get_metrics(self, symbol):
        self._company(symbol)
        return {"market_cap": 3.4e12, "pe": 31.0, "week52_low": 160.0, "week52_high": 260.0}

    def search_symbols(self, query):
        return [{"symbol": s, "name": c["name"], "type": "Common Stock"}
                for s, c in self.COMPANIES.items() if query.lower() in c["name"].lower()]


class FakeNews(Provider):
    name = "fakenews"
    label = "Fake news"

    def __init__(self):
        self.company_calls = []

    def get_company_news(self, symbol, company_name="", limit=3):
        self.company_calls.append(symbol)
        return [{"title": f"{symbol} story {i}", "summary": "Body", "url": f"https://x.example/{symbol}/{i}",
                 "source": "Wire", "published": None, "image": None} for i in range(limit)]

    def get_market_news(self, limit=5):
        return [{"title": f"Market story {i}", "summary": "", "url": f"https://x.example/m/{i}",
                 "source": "Wire", "published": None, "image": None} for i in range(limit)]
