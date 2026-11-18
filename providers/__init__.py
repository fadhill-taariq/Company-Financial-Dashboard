"""Data providers and the registry that picks them from config.

Adding a provider takes three steps:
  1. Write a class that subclasses providers.base.Provider and implements
     whichever methods its API supports.
  2. Add it to REGISTRY below, keyed by the name used in config.json.
  3. Put its name against one or more roles under "providers" in config.json.
"""

from .alpha_vantage import AlphaVantageProvider
from .base import CachedProvider, NotSupported, Provider, ProviderError
from .finnhub import FinnhubProvider
from .newsapi import NewsAPIProvider
from .sample import SAMPLE_LABEL, SampleProvider

REGISTRY = {
    "finnhub": FinnhubProvider,
    "alpha_vantage": AlphaVantageProvider,
    "newsapi": NewsAPIProvider,
    "sample": SampleProvider,
}

ROLES = ("market_data", "price_history", "company_news", "market_news")


def build_providers(settings: dict) -> dict:
    """Return {role: provider} for every role, built from the settings.

    Providers named for more than one role are shared, so they also share a cache.
    """
    keys = settings.get("api_keys", {})
    ttl = float(settings.get("cache_minutes", 10)) * 60
    built = {}
    roles = {}
    for role in ROLES:
        name = settings.get("providers", {}).get(role) or "sample"
        if name not in REGISTRY:
            raise ValueError(f"Unknown provider {name!r} for {role}; "
                             f"choose from {', '.join(sorted(REGISTRY))}")
        if name not in built:
            cls = REGISTRY[name]
            inner = cls() if name == "sample" else cls(api_key=keys.get(name, ""))
            built[name] = CachedProvider(inner, ttl_seconds=ttl)
        roles[role] = built[name]
    return roles


__all__ = ["Provider", "ProviderError", "NotSupported", "CachedProvider",
           "FinnhubProvider", "AlphaVantageProvider", "NewsAPIProvider",
           "SampleProvider", "SAMPLE_LABEL", "REGISTRY", "ROLES", "build_providers"]
