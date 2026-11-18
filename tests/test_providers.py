from datetime import date

import pytest

from config import DEFAULTS
from providers import (AlphaVantageProvider, CachedProvider, FinnhubProvider,
                       NewsAPIProvider, NotSupported, ProviderError, SampleProvider,
                       build_providers)
from providers.base import to_float
from tests.fakes import FakeMarket, FakeSession


def test_to_float_handles_api_placeholders():
    assert to_float("1.5%") == 1.5
    assert to_float("1,234.5") == 1234.5
    assert to_float("None") is None
    assert to_float("-") is None
    assert to_float(None) is None
    assert to_float(0) == 0.0


# --- Finnhub -----------------------------------------------------------------

FINNHUB_ROUTES = {
    "/stock/profile2": {"name": "NVIDIA Corp", "ticker": "NVDA", "exchange": "NASDAQ",
                        "currency": "USD", "country": "US", "finnhubIndustry": "Semiconductors",
                        "logo": "https://logo.example/nvda.png", "weburl": "https://nvidia.com"},
    "/quote": {"c": 186.4, "d": 3.12, "dp": 1.7, "h": 188, "l": 182, "o": 183, "pc": 183.28},
    "/stock/metric": {"metric": {"marketCapitalization": 4540000, "peTTM": 38.5,
                                 "52WeekHigh": 212.2, "52WeekLow": 140.8,
                                 "5DayPriceReturnDaily": 2.4,
                                 "priceRelativeToS&P50052Week": 14.9}},
    "/company-news": [
        {"headline": "Older story", "datetime": 1700000000, "url": "https://a", "source": "A"},
        {"headline": "Newer story", "datetime": 1800000000, "url": "https://b", "source": "B"},
        {"headline": "newer story", "datetime": 1700000001, "url": "https://c"},
        {"headline": "", "datetime": 1800000001},
    ],
    "/news": [{"headline": f"Market {i}", "datetime": i} for i in range(10)],
    "/search": {"result": [{"symbol": "NVDA", "description": "NVIDIA CORP", "type": "Common Stock"},
                           {"symbol": "NVD.DE", "description": "NVIDIA CORP", "type": "Common Stock"}]},
}


def finnhub(routes=FINNHUB_ROUTES, key="secret"):
    session = FakeSession(routes)
    return FinnhubProvider(key, session=session, today=lambda: date(2026, 11, 17)), session


def test_finnhub_parses_profile_quote_and_metrics():
    provider, session = finnhub()
    assert provider.get_profile("NVDA")["industry"] == "Semiconductors"
    assert provider.get_quote("NVDA")["change_pct"] == 1.7
    metrics = provider.get_metrics("NVDA")
    assert metrics["market_cap"] == 4.54e12  # Finnhub reports millions
    assert metrics["rel_sp500_52w"] == 14.9
    assert metrics["beta"] is None
    # The key travels in a header, never in the URL
    assert session.calls[0]["headers"] == {"X-Finnhub-Token": "secret"}
    assert "token" not in session.calls[0]["params"]


def test_finnhub_company_news_is_newest_first_without_duplicates():
    provider, session = finnhub()
    articles = provider.get_company_news("NVDA", limit=5)
    assert [a["title"] for a in articles] == ["Newer story", "Older story"]
    assert session.calls[0]["params"]["from"] == "2026-11-10"
    assert len(provider.get_market_news(limit=3)) == 3


def test_finnhub_search_keeps_us_listings_only():
    provider, _ = finnhub()
    assert [m["symbol"] for m in provider.search_symbols("nvidia")] == ["NVDA"]


def test_finnhub_unknown_symbol_and_missing_key_raise():
    provider, _ = finnhub({"/quote": {"c": 0, "d": None, "dp": None}})
    with pytest.raises(ProviderError):
        provider.get_quote("NOPE")
    with pytest.raises(ProviderError):
        FinnhubProvider("").get_quote("NVDA")
    with pytest.raises(NotSupported):
        provider.get_price_history("NVDA")


def test_http_errors_become_provider_errors_without_leaking_the_key(caplog):
    provider = AlphaVantageProvider("secret", session=FakeSession({}, status=500))
    with pytest.raises(ProviderError):
        provider.get_quote("NVDA")
    assert "secret" not in caplog.text


# --- Alpha Vantage -----------------------------------------------------------

def av_route(function):
    return lambda url, params: params.get("function") == function


AV_ROUTES = {
    av_route("GLOBAL_QUOTE"): {"Global Quote": {"05. price": "186.40", "09. change": "3.12",
                                                "10. change percent": "1.7000%"}},
    av_route("OVERVIEW"): {"Symbol": "NVDA", "Name": "NVIDIA Corporation", "Exchange": "NASDAQ",
                           "Industry": "SEMICONDUCTORS", "MarketCapitalization": "4540000000000",
                           "PERatio": "38.5", "Beta": "None", "DividendYield": "0.0002",
                           "ProfitMargin": "0.556"},
    av_route("TIME_SERIES_DAILY"): {"Time Series (Daily)": {
        "2026-11-14": {"4. close": "186.40"}, "2026-11-13": {"4. close": "183.28"}}},
    av_route("NEWS_SENTIMENT"): {"feed": [{"title": "Story", "url": "https://s",
                                           "time_published": "20261117T153000", "source": "S"}]},
}


def test_alpha_vantage_parses_quote_metrics_and_history():
    provider = AlphaVantageProvider("k", session=FakeSession(AV_ROUTES))
    assert provider.get_quote("NVDA")["change_pct"] == 1.7
    assert provider.get_profile("NVDA")["industry"] == "Semiconductors"
    metrics = provider.get_metrics("NVDA")
    assert metrics["beta"] is None
    assert metrics["dividend_yield"] == pytest.approx(0.02)
    assert metrics["net_margin"] == pytest.approx(55.6)
    history = provider.get_price_history("NVDA")
    assert [p["date"] for p in history] == ["2026-11-13", "2026-11-14"]
    news = provider.get_company_news("NVDA")
    assert news[0]["published"].hour == 15


def test_alpha_vantage_quota_message_raises():
    session = FakeSession({av_route("GLOBAL_QUOTE"): {"Information": "25 requests per day"}})
    with pytest.raises(ProviderError, match="25 requests"):
        AlphaVantageProvider("k", session=session).get_quote("NVDA")


# --- NewsAPI -----------------------------------------------------------------

def test_newsapi_searches_company_name_and_ticker():
    session = FakeSession({"/everything": {"articles": [
        {"title": "A", "description": "a", "url": "https://a", "source": {"name": "Src"},
         "publishedAt": "2026-11-17T10:00:00Z"},
        {"title": "[Removed]"}]}})
    provider = NewsAPIProvider("k", session=session)
    articles = provider.get_company_news("NVDA", "NVIDIA Corp")
    assert session.calls[0]["params"]["q"] == '"NVIDIA" OR "NVDA"'
    assert [a["title"] for a in articles] == ["A"]
    assert articles[0]["source"] == "Src"
    with pytest.raises(NotSupported):
        provider.get_quote("NVDA")


# --- Sample, cache and registry ----------------------------------------------

def test_sample_provider_has_nvda_and_searches_by_name():
    sample = SampleProvider()
    assert sample.get_profile("nvda")["name"] == "NVIDIA Corp"
    assert len(sample.get_price_history("NVDA")) == 90
    assert sample.search_symbols("nvidia")[0]["symbol"] == "NVDA"
    with pytest.raises(ProviderError):
        sample.get_quote("AAPL")


def test_cached_provider_reuses_answers_until_they_expire():
    clock = [0.0]
    inner = FakeMarket()
    cached = CachedProvider(inner, ttl_seconds=60, clock=lambda: clock[0])
    cached.get_quote("AAPL")
    cached.get_quote("AAPL")
    assert inner.calls == ["AAPL"]
    clock[0] = 61
    cached.get_quote("AAPL")
    assert inner.calls == ["AAPL", "AAPL"]


def test_build_providers_shares_one_instance_per_provider():
    settings = {**DEFAULTS, "providers": {"market_data": "finnhub", "price_history": "alpha_vantage",
                                          "company_news": "finnhub", "market_news": "newsapi"}}
    roles = build_providers(settings)
    assert roles["market_data"] is roles["company_news"]
    assert roles["market_news"].name == "newsapi"
    with pytest.raises(ValueError):
        build_providers({**DEFAULTS, "providers": {"market_data": "bloomberg"}})
