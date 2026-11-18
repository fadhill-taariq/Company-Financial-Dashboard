from company_data_handler import get_company_data, normalise_symbol
from providers import SAMPLE_LABEL, SampleProvider
from tests.fakes import FailingProvider, FakeMarket


def providers(market, history=None):
    return {"market_data": market, "price_history": history or FailingProvider()}


def test_normalise_symbol():
    assert normalise_symbol(" nvda ") == "NVDA"
    assert normalise_symbol("BRK.B") == "BRK.B"
    assert normalise_symbol("nvidia corp") is None
    assert normalise_symbol("") is None


def test_live_data_with_benchmark_comparison():
    data = get_company_data("AAPL", providers(FakeMarket()))
    assert data["available"] and not data["is_sample"]
    assert data["source"] == "Fake market data"
    assert data["profile"]["name"] == "Apple Inc"
    assert data["benchmark"]["change_pct"] == 0.25
    # Metrics the provider didn't supply are present as None
    assert data["metrics"]["beta"] is None
    # The missing chart is explained rather than hidden
    assert data["history"] is None
    assert any("Price chart unavailable" in note for note in data["notes"])


def test_falls_back_to_labelled_sample_data():
    data = get_company_data("NVDA", providers(FailingProvider()), sample=SampleProvider())
    assert data["available"] and data["is_sample"]
    assert data["source"] == SAMPLE_LABEL
    assert data["benchmark"]["change_pct"] is not None
    assert data["history"]


def test_unknown_company_with_no_sample_is_unavailable():
    data = get_company_data("ZZZZ", providers(FailingProvider()))
    assert not data["available"]
    assert "ZZZZ" in data["message"]
    assert "NVDA" in data["message"]
