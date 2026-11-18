from news_handling import NewsStore
from tests.fakes import FailingProvider, FakeNews


def test_shows_company_and_market_news_up_to_their_limits():
    store = NewsStore(FakeNews(), FakeNews(), company_count=3, market_count=5)
    store.set_company("NVDA", "NVIDIA Corp")
    store.update_news()
    assert [a["title"] for a in store.visible_company()] == ["NVDA story 0", "NVDA story 1", "NVDA story 2"]
    assert len(store.visible_market()) == 5


def test_dismissed_articles_stay_hidden_and_are_replaced():
    store = NewsStore(FakeNews(), FakeNews())
    store.set_company("NVDA")
    store.update_news()
    store.remove("https://x.example/NVDA/0")
    store.update_news()
    titles = [a["title"] for a in store.visible_company()]
    assert "NVDA story 0" not in titles
    assert len(titles) == 3


def test_switching_company_replaces_its_stories():
    news = FakeNews()
    store = NewsStore(news, news)
    store.set_company("NVDA")
    store.update_news()
    store.set_company("AAPL")
    assert store.visible_company() == []
    store.update_news()
    assert store.visible_company()[0]["title"] == "AAPL story 0"


def test_failures_are_reported_not_raised():
    store = NewsStore(FailingProvider(), FailingProvider())
    store.set_company("NVDA")
    store.update_news()
    assert store.visible_company() == []
    assert "No API key" in store.company_note
    assert "No API key" in store.market_note
