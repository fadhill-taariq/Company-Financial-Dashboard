"""Load dashboard settings from config.json, with environment-variable overrides.

Copy config.example.json to config.json and fill in your own values.
API keys can also be supplied as environment variables so they never have to
be written to a file:

    FINNHUB_API_KEY, ALPHA_VANTAGE_API_KEY, NEWS_API_KEY
"""

import copy
import json
import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
EXAMPLE_CONFIG_PATH = os.path.join(BASE_DIR, "config.example.json")

DEFAULTS = {
    "default_symbol": "NVDA",
    "benchmark_symbol": "SPY",
    "benchmark_name": "S&P 500 (SPY)",
    "providers": {
        "market_data": "finnhub",
        "price_history": "alpha_vantage",
        "company_news": "finnhub",
        "market_news": "finnhub",
    },
    "api_keys": {"finnhub": "", "alpha_vantage": "", "newsapi": ""},
    "company_news_count": 3,
    "market_news_count": 5,
    "cache_minutes": 10,
}

ENV_KEYS = {
    "finnhub": "FINNHUB_API_KEY",
    "alpha_vantage": "ALPHA_VANTAGE_API_KEY",
    "newsapi": "NEWS_API_KEY",
}


def load_config(path: str = CONFIG_PATH) -> dict:
    """Return the dashboard settings, falling back to defaults for anything missing."""
    settings = copy.deepcopy(DEFAULTS)
    source = path if os.path.exists(path) else EXAMPLE_CONFIG_PATH
    try:
        with open(source, "r", encoding="utf-8") as file:
            loaded = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        logging.warning("Could not read config file %s: %s", source, error)
        loaded = {}

    for key, value in loaded.items():
        # Nested sections are merged so a partial config keeps the other defaults
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key].update(value)
        else:
            settings[key] = value

    for name, env_var in ENV_KEYS.items():
        if os.environ.get(env_var):
            settings["api_keys"][name] = os.environ[env_var]
    return settings
