"""Company and market news for the dashboard.

Two lists are kept: stories about the selected company, and general financial
news. As in the COVID dashboard, dismissed articles stay hidden after later
refreshes.
"""

import logging

from providers import ProviderError


class NewsStore:
    """Holds the current headlines and remembers any the user has dismissed."""

    def __init__(self, company_provider=None, market_provider=None,
                 company_count: int = 3, market_count: int = 5):
        self.company_provider = company_provider
        self.market_provider = market_provider
        self.company_count = company_count
        self.market_count = market_count
        self.symbol = ""
        self.company_name = ""
        self.company_articles = []
        self.market_articles = []
        self.company_note = None
        self.market_note = None
        self.removed = set()

    def set_company(self, symbol: str, company_name: str = "") -> None:
        """Switch to another company; its stories replace the old ones."""
        if symbol != self.symbol:
            self.company_articles = []
        self.symbol = symbol
        self.company_name = company_name

    def update_news(self, update_name: str = "") -> None:
        """Fetch fresh company and market headlines."""
        # Fetch a few spare articles so dismissing one leaves the panel full
        if self.company_provider and self.symbol:
            try:
                self.company_articles = self.company_provider.get_company_news(
                    self.symbol, self.company_name, self.company_count + 10)
                self.company_note = None
            except ProviderError as error:
                self.company_note = str(error)
                logging.warning("Company news unavailable: %s", error)

        if self.market_provider:
            try:
                self.market_articles = self.market_provider.get_market_news(
                    self.market_count + 10)
                self.market_note = None
            except ProviderError as error:
                self.market_note = str(error)
                logging.warning("Market news unavailable: %s", error)

        logging.info("News update %r: %d company, %d market articles", update_name,
                     len(self.company_articles), len(self.market_articles))

    @staticmethod
    def key(article: dict) -> str:
        return article.get("url") or article["title"]

    def remove(self, key: str) -> None:
        """Dismiss an article so it won't come back on later updates."""
        self.removed.add(key)

    def _visible(self, articles, count, exclude=()):
        shown = [a for a in articles
                 if self.key(a) not in self.removed and self.key(a) not in exclude]
        return shown[:count]

    def visible_company(self) -> list:
        return self._visible(self.company_articles, self.company_count)

    def visible_market(self) -> list:
        # A story can turn up in both feeds; show it only under the company
        company_keys = {self.key(a) for a in self.visible_company()}
        return self._visible(self.market_articles, self.market_count, company_keys)
