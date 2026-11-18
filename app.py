"""Company financial dashboard - Flask entry point.

Run with:  python app.py   then open http://127.0.0.1:5000/index
"""

import logging

from flask import Flask, redirect, render_template, request, url_for

import formatting
from company_data_handler import get_company_data, normalise_symbol
from config import load_config
from news_handling import NewsStore
from providers import ProviderError, SampleProvider, build_providers
from update_scheduler import UpdateScheduler

logging.basicConfig(
    filename="events.log",
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

MAX_MATCHES = 8


def create_app(settings: dict = None, providers: dict = None,
               sample: SampleProvider = None) -> Flask:
    """Build the Flask app. Arguments allow tests to swap in fake providers."""
    settings = settings or load_config()
    providers = providers or build_providers(settings)
    sample = sample or SampleProvider()
    app = Flask(__name__)
    formatting.register(app)

    news = NewsStore(providers["company_news"], providers["market_news"],
                     int(settings["company_news_count"]),
                     int(settings["market_news_count"]))

    def fetch(symbol):
        return get_company_data(symbol, providers, settings["benchmark_symbol"],
                                settings["benchmark_name"], sample=sample)

    state = {"company": fetch(settings["default_symbol"])}
    news.set_company(state["company"]["symbol"], state["company"]["profile"]["name"])
    news.update_news("startup")

    def switch_company(symbol):
        """Load another company. Returns an error message, or None on success."""
        data = fetch(symbol)
        if not data["available"]:
            return data["message"]
        state["company"] = data
        news.set_company(symbol, data["profile"]["name"])
        news.update_news(f"switch to {symbol}")
        return None

    def update_market():
        state["company"] = fetch(state["company"]["symbol"])

    def search(text):
        """Return (symbol to switch to, matches to offer, error)."""
        wanted = normalise_symbol(text)
        try:
            matches = providers["market_data"].search_symbols(text.strip())
        except ProviderError as error:
            logging.info("Symbol search unavailable: %s", error)
            matches = sample.search_symbols(text.strip())
        exact = [m for m in matches if m["symbol"] == wanted]
        if exact:
            return wanted, [], None
        if len(matches) == 1:
            return matches[0]["symbol"], [], None
        if matches:
            return None, matches[:MAX_MATCHES], None
        if wanted:  # nothing found by name, but it looks like a ticker: try it directly
            return wanted, [], None
        return None, [], f"No companies found for {text.strip()!r}"

    scheduler = UpdateScheduler(update_market, news.update_news)
    app.config.update(scheduler=scheduler, news=news, state=state)

    @app.route("/")
    def home():
        return redirect(url_for("index"))

    @app.route("/index")
    def index():
        scheduler.run_pending()
        args = request.args
        matches, query = [], ""

        if args.get("notif"):
            news.remove(args["notif"])
            return redirect(url_for("index"))

        if args.get("update_item"):
            scheduler.cancel(args["update_item"])
            return redirect(url_for("index"))

        if args.get("refresh"):
            for provider in set(providers.values()):
                if hasattr(provider, "clear"):
                    provider.clear()
            update_market()
            news.update_news("manual refresh")
            return redirect(url_for("index"))

        if args.get("symbol"):
            symbol = normalise_symbol(args["symbol"])
            error = switch_company(symbol) if symbol else "That isn't a valid ticker symbol"
            return redirect(url_for("index", error=error) if error else url_for("index"))

        if args.get("company"):
            query = args["company"]
            symbol, matches, error = search(query)
            if symbol:
                error = switch_company(symbol)
                return redirect(url_for("index", error=error) if error else url_for("index"))
            if error:
                return redirect(url_for("index", error=error))

        if args.get("two"):
            try:
                scheduler.add(
                    title=args["two"],
                    hhmm=args.get("update", ""),
                    repeat="repeat" in args,
                    market="market-data" in args,
                    news="news" in args,
                )
            except ValueError as error:
                logging.warning("Rejected scheduled update: %s", error)
                return redirect(url_for("index", error=str(error)))
            return redirect(url_for("index"))

        company = state["company"]
        return render_template(
            "index.html",
            company=company,
            chart=formatting.price_chart(company["history"]),
            company_news=news.visible_company(),
            market_news=news.visible_market(),
            company_news_note=news.company_note,
            market_news_note=news.market_note,
            updates=scheduler.updates,
            matches=matches,
            query=query,
            error=args.get("error"),
        )

    return app


if __name__ == "__main__":
    create_app().run()
