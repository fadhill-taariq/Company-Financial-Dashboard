"""Finnhub (https://finnhub.io) - quotes, profiles, key metrics, news and search.

The free key covers US-listed companies at about 60 requests a minute.
Daily price history (candles) is a paid endpoint, so it isn't used here;
the dashboard gets its chart from Alpha Vantage instead.
"""

from datetime import date, datetime, timedelta, timezone

from .base import NotSupported, Provider, ProviderError, first_present, request_json, to_float

BASE_URL = "https://finnhub.io/api/v1"


class FinnhubProvider(Provider):
    name = "finnhub"
    label = "Finnhub"

    def __init__(self, api_key: str = "", session=None, today=date.today):
        self.api_key = api_key
        self.session = session
        self._today = today

    def _get(self, path: str, **params):
        if not self.api_key:
            raise ProviderError("No Finnhub API key configured")
        # The key goes in a header rather than the URL, so it can't leak into logs
        return request_json(self.session, f"{BASE_URL}{path}", params,
                            headers={"X-Finnhub-Token": self.api_key},
                            label="Finnhub")

    def get_profile(self, symbol):
        data = self._get("/stock/profile2", symbol=symbol)
        if not data or not data.get("name"):
            raise ProviderError(f"Finnhub has no profile for {symbol}")
        return {
            "symbol": data.get("ticker") or symbol,
            "name": data.get("name"),
            "exchange": data.get("exchange"),
            "currency": data.get("currency") or "USD",
            "country": data.get("country"),
            "industry": data.get("finnhubIndustry"),
            "logo": data.get("logo") or None,
            "website": data.get("weburl") or None,
        }

    def get_quote(self, symbol):
        data = self._get("/quote", symbol=symbol)
        price = to_float(data.get("c"))
        # Finnhub answers unknown symbols with zeros rather than an error
        if not price:
            raise ProviderError(f"Finnhub has no quote for {symbol}")
        return {
            "price": price,
            "change": to_float(data.get("d")),
            "change_pct": to_float(data.get("dp")),
            "high": to_float(data.get("h")),
            "low": to_float(data.get("l")),
            "open": to_float(data.get("o")),
            "prev_close": to_float(data.get("pc")),
        }

    def get_metrics(self, symbol):
        data = self._get("/stock/metric", symbol=symbol, metric="all")
        m = (data or {}).get("metric") or {}
        if not m:
            raise ProviderError(f"Finnhub has no metrics for {symbol}")
        market_cap_millions = first_present(m, "marketCapitalization")
        return {
            "market_cap": market_cap_millions * 1e6 if market_cap_millions else None,
            "pe": first_present(m, "peTTM", "peBasicExclExtraTTM", "peExclExtraTTM"),
            "eps": first_present(m, "epsTTM", "epsBasicExclExtraItemsTTM", "epsExclExtraItemsTTM"),
            "beta": first_present(m, "beta"),
            "week52_high": first_present(m, "52WeekHigh"),
            "week52_low": first_present(m, "52WeekLow"),
            "dividend_yield": first_present(m, "currentDividendYieldTTM",
                                            "dividendYieldIndicatedAnnual"),
            "return_5d": first_present(m, "5DayPriceReturnDaily"),
            "return_ytd": first_present(m, "yearToDatePriceReturnDaily"),
            "return_52w": first_present(m, "52WeekPriceReturnDaily"),
            "rel_sp500_52w": first_present(m, "priceRelativeToS&P50052Week"),
            "net_margin": first_present(m, "netProfitMarginTTM"),
            "revenue_growth": first_present(m, "revenueGrowthTTMYoy"),
        }

    def get_price_history(self, symbol):
        raise NotSupported("Finnhub's free tier does not include price history")

    def get_company_news(self, symbol, company_name="", limit=3):
        today = self._today()
        data = self._get("/company-news", symbol=symbol,
                         **{"from": (today - timedelta(days=7)).isoformat(),
                            "to": today.isoformat()})
        return _articles(data, limit)

    def get_market_news(self, limit=5):
        return _articles(self._get("/news", category="general"), limit)

    def search_symbols(self, query):
        data = self._get("/search", q=query)
        matches = []
        for item in (data or {}).get("result", []):
            symbol = item.get("symbol") or ""
            # The free tier covers US listings, which have no exchange suffix
            if not symbol or "." in symbol:
                continue
            matches.append({"symbol": symbol,
                            "name": item.get("description") or symbol,
                            "type": item.get("type") or ""})
        return matches


def _articles(items, limit):
    """Turn Finnhub news items into standard articles, newest first, no repeats."""
    articles, seen = [], set()
    for item in sorted(items or [], key=lambda i: i.get("datetime") or 0, reverse=True):
        title = (item.get("headline") or "").strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        stamp = item.get("datetime")
        articles.append({
            "title": title,
            "summary": item.get("summary") or "",
            "url": item.get("url") or "",
            "source": item.get("source") or "",
            "published": datetime.fromtimestamp(stamp, tz=timezone.utc) if stamp else None,
            "image": item.get("image") or None,
        })
        if len(articles) >= limit:
            break
    return articles
