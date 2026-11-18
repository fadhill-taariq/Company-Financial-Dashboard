"""Alpha Vantage (https://www.alphavantage.co) - quotes, fundamentals, history, news.

The free key allows 25 requests a day, so by default the dashboard only uses
it for the price chart. It can also stand in for Finnhub entirely; set it as
the market_data provider in config.json.
"""

from datetime import datetime, timezone

from .base import Provider, ProviderError, first_present, request_json, to_float

BASE_URL = "https://www.alphavantage.co/query"
HISTORY_DAYS = 90


class AlphaVantageProvider(Provider):
    name = "alpha_vantage"
    label = "Alpha Vantage"

    def __init__(self, api_key: str = "", session=None):
        self.api_key = api_key
        self.session = session

    def _get(self, function: str, **params):
        if not self.api_key:
            raise ProviderError("No Alpha Vantage API key configured")
        data = request_json(self.session, BASE_URL,
                            {"function": function, "apikey": self.api_key, **params},
                            label="Alpha Vantage")
        # Errors and quota messages come back as 200 responses with one of these keys
        for key in ("Error Message", "Information", "Note"):
            if isinstance(data, dict) and key in data:
                raise ProviderError(f"Alpha Vantage: {data[key]}")
        return data

    def get_profile(self, symbol):
        data = self._overview(symbol)
        return {
            "symbol": data.get("Symbol") or symbol,
            "name": data.get("Name"),
            "exchange": data.get("Exchange"),
            "currency": data.get("Currency") or "USD",
            "country": data.get("Country"),
            "industry": (data.get("Industry") or "").title() or None,
            "logo": None,
            "website": data.get("OfficialSite") or None,
        }

    def get_quote(self, symbol):
        data = self._get("GLOBAL_QUOTE", symbol=symbol).get("Global Quote") or {}
        price = to_float(data.get("05. price"))
        if not price:
            raise ProviderError(f"Alpha Vantage has no quote for {symbol}")
        return {
            "price": price,
            "change": to_float(data.get("09. change")),
            "change_pct": to_float(data.get("10. change percent")),
            "high": to_float(data.get("03. high")),
            "low": to_float(data.get("04. low")),
            "open": to_float(data.get("02. open")),
            "prev_close": to_float(data.get("08. previous close")),
        }

    def get_metrics(self, symbol):
        d = self._overview(symbol)

        def pct(key):  # Alpha Vantage gives ratios such as 0.55 for 55%
            value = to_float(d.get(key))
            return value * 100 if value is not None else None

        return {
            "market_cap": first_present(d, "MarketCapitalization"),
            "pe": first_present(d, "PERatio", "TrailingPE"),
            "eps": first_present(d, "EPS"),
            "beta": first_present(d, "Beta"),
            "week52_high": first_present(d, "52WeekHigh"),
            "week52_low": first_present(d, "52WeekLow"),
            "dividend_yield": pct("DividendYield"),
            "return_5d": None,
            "return_ytd": None,
            "return_52w": None,
            "rel_sp500_52w": None,
            "net_margin": pct("ProfitMargin"),
            "revenue_growth": pct("QuarterlyRevenueGrowthYOY"),
        }

    def get_price_history(self, symbol):
        data = self._get("TIME_SERIES_DAILY", symbol=symbol, outputsize="compact")
        series = data.get("Time Series (Daily)") or {}
        if not series:
            raise ProviderError(f"Alpha Vantage has no price history for {symbol}")
        points = []
        for day in sorted(series)[-HISTORY_DAYS:]:
            close = to_float(series[day].get("4. close"))
            if close is not None:
                points.append({"date": day, "close": close})
        return points

    def get_company_news(self, symbol, company_name="", limit=3):
        data = self._get("NEWS_SENTIMENT", tickers=symbol, sort="LATEST", limit=50)
        return _articles(data, limit)

    def get_market_news(self, limit=5):
        data = self._get("NEWS_SENTIMENT", topics="financial_markets",
                         sort="LATEST", limit=50)
        return _articles(data, limit)

    def search_symbols(self, query):
        data = self._get("SYMBOL_SEARCH", keywords=query)
        return [{"symbol": m.get("1. symbol"), "name": m.get("2. name"),
                 "type": m.get("3. type") or ""}
                for m in data.get("bestMatches", []) if m.get("1. symbol")]

    def _overview(self, symbol):
        data = self._get("OVERVIEW", symbol=symbol)
        if not data or not data.get("Name"):
            raise ProviderError(f"Alpha Vantage has no overview for {symbol}")
        return data


def _articles(data, limit):
    articles, seen = [], set()
    for item in (data or {}).get("feed", []):
        title = (item.get("title") or "").strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        published = None
        try:
            published = datetime.strptime(item.get("time_published", ""),
                                          "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        articles.append({
            "title": title,
            "summary": item.get("summary") or "",
            "url": item.get("url") or "",
            "source": item.get("source") or "",
            "published": published,
            "image": item.get("banner_image") or None,
        })
        if len(articles) >= limit:
            break
    return articles
