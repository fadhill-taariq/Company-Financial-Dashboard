"""NewsAPI (https://newsapi.org) - news only, the same source the COVID dashboard used.

Set it as the company_news and/or market_news provider in config.json.
"""

from datetime import datetime

from .base import Provider, ProviderError, request_json

EVERYTHING_URL = "https://newsapi.org/v2/everything"
HEADLINES_URL = "https://newsapi.org/v2/top-headlines"


class NewsAPIProvider(Provider):
    name = "newsapi"
    label = "NewsAPI"

    def __init__(self, api_key: str = "", session=None):
        self.api_key = api_key
        self.session = session

    def _get(self, url, **params):
        if not self.api_key:
            raise ProviderError("No NewsAPI key configured")
        data = request_json(self.session, url, params,
                            headers={"X-Api-Key": self.api_key}, label="NewsAPI")
        if data.get("status") == "error":
            raise ProviderError(f"NewsAPI: {data.get('message', 'error')}")
        return data

    def get_company_news(self, symbol, company_name="", limit=3):
        # Searching the ticker alone matches too loosely ("ON", "ALL"), so the
        # company name is used when known, e.g. "NVIDIA" OR "NVDA"
        terms = [f'"{_short_name(company_name)}"'] if company_name else []
        terms.append(f'"{symbol}"')
        data = self._get(EVERYTHING_URL, q=" OR ".join(terms), language="en",
                         sortBy="publishedAt", pageSize=20)
        return _articles(data, limit)

    def get_market_news(self, limit=5):
        data = self._get(HEADLINES_URL, category="business", language="en",
                         pageSize=20)
        return _articles(data, limit)


def _short_name(name: str) -> str:
    """'NVIDIA Corp' -> 'NVIDIA', so articles that drop the suffix still match."""
    suffixes = {"inc", "inc.", "corp", "corp.", "corporation", "plc", "ltd",
                "ltd.", "co", "co.", "company", "holdings", "group", "sa", "ag", "nv"}
    words = [w for w in name.replace(",", "").split() if w.lower() not in suffixes]
    return " ".join(words) or name


def _articles(data, limit):
    articles, seen = [], set()
    for item in data.get("articles", []):
        title = (item.get("title") or "").strip()
        if not title or title == "[Removed]" or title.lower() in seen:
            continue
        seen.add(title.lower())
        published = None
        try:
            published = datetime.fromisoformat(
                (item.get("publishedAt") or "").replace("Z", "+00:00"))
        except ValueError:
            pass
        articles.append({
            "title": title,
            "summary": item.get("description") or "",
            "url": item.get("url") or "",
            "source": (item.get("source") or {}).get("name") or "",
            "published": published,
            "image": item.get("urlToImage") or None,
        })
        if len(articles) >= limit:
            break
    return articles
