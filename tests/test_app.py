import pytest

from app import create_app
from config import DEFAULTS
from tests.fakes import FailingProvider, FakeMarket, FakeNews


def make_client(market=None):
    market = market or FakeMarket()
    news = FakeNews()
    settings = {**DEFAULTS, "default_symbol": "AAPL"}
    app = create_app(settings, providers={
        "market_data": market, "price_history": FailingProvider(),
        "company_news": news, "market_news": news})
    return app.test_client(), app


@pytest.fixture
def client():
    return make_client()


def page(test_client, url="/index"):
    return test_client.get(url, follow_redirects=True).get_data(as_text=True)


def test_dashboard_shows_company_figures_and_news(client):
    test_client, _ = client
    html = page(test_client)
    assert "Apple Inc" in html
    assert "$230.00" in html
    assert "$3.40T" in html
    assert "AAPL story 0" in html
    assert "Market story 0" in html
    assert "sample data" not in html.lower()


def test_search_by_name_switches_company(client):
    test_client, app = client
    html = page(test_client, "/index?company=microsoft")
    assert "Microsoft Corp" in html
    assert "MSFT story 0" in html
    assert app.config["state"]["company"]["symbol"] == "MSFT"


def test_ambiguous_search_offers_choices(client):
    test_client, _ = client
    html = page(test_client, "/index?company=p")  # matches Apple, SPDR and Microsoft
    assert "Did you mean" in html
    assert "/index?symbol=MSFT" in html


def test_unknown_company_keeps_current_one_and_explains(client):
    test_client, app = client
    html = page(test_client, "/index?symbol=ZZZZ")
    assert "Couldn&#39;t load data for ZZZZ" in html
    assert app.config["state"]["company"]["symbol"] == "AAPL"


def test_no_keys_falls_back_to_sample_data():
    test_client, _ = make_client(market=FailingProvider())
    # AAPL has no sample data, so the dashboard explains; NVDA does
    assert "Couldn" in page(test_client)
    html = page(test_client, "/index?symbol=NVDA")
    assert "NVIDIA Corp" in html
    assert "sample data" in html.lower()
    assert "Closing price" in html and "<polyline" in html


def test_schedule_and_cancel_update(client):
    test_client, app = client
    response = test_client.get(
        "/index?update=15:15&two=Open&repeat=repeat&market-data=market-data")
    assert response.status_code == 302
    assert "Open" in page(test_client)
    test_client.get("/index?update_item=Open")
    assert app.config["scheduler"].updates == []


def test_dismiss_news(client):
    test_client, _ = client
    test_client.get("/index?notif=https://x.example/AAPL/0")
    assert "AAPL story 0" not in page(test_client)


def test_invalid_update_shows_error(client):
    test_client, _ = client
    assert "Choose market data, news, or both" in page(test_client, "/index?update=15:15&two=NoBoxes")
