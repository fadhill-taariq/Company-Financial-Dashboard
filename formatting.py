"""Number formatting and chart geometry for the dashboard template."""

import math
from datetime import date

CURRENCY_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥", "CNY": "¥",
                    "INR": "₹", "CAD": "C$", "AUD": "A$", "CHF": "CHF "}


def currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get((code or "USD").upper(), f"{code} ")


def money(value, currency="USD", compact=False) -> str:
    """$186.40, or with compact=True $4.54T / $812.3B / $95.1M."""
    if value is None:
        return "Not available"
    sign = "-" if value < 0 else ""
    value = abs(value)
    prefix = currency_symbol(currency)
    if compact:
        for size, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if value >= size:
                return f"{sign}{prefix}{value / size:,.2f}{suffix}"
    return f"{sign}{prefix}{value:,.2f}"


def pct(value, signed=True, places=2) -> str:
    """+1.70% / -0.43% / 55.60%."""
    if value is None:
        return "Not available"
    return f"{value:+,.{places}f}%" if signed else f"{value:,.{places}f}%"


def number(value, places=2) -> str:
    if value is None:
        return "Not available"
    return f"{value:,.{places}f}"


def direction(value) -> str:
    """'up', 'down' or 'flat' - used for colour classes and arrows."""
    if value is None or abs(value) < 0.005:
        return "flat"
    return "up" if value > 0 else "down"


def range_position(price, low, high):
    """Where the price sits in its 52-week range, as 0-100, or None."""
    if None in (price, low, high) or high <= low:
        return None
    return max(0.0, min(100.0, (price - low) / (high - low) * 100))


def _nice_step(span: float, target_ticks: int = 4) -> float:
    raw = span / max(target_ticks, 1)
    magnitude = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for multiple in (1, 2, 2.5, 5, 10):
        if raw <= multiple * magnitude:
            return multiple * magnitude
    return 10 * magnitude


def price_chart(history, width=400, height=190, pad_left=40, pad_right=12,
                pad_top=12, pad_bottom=26):
    """Work out an SVG line chart for [{date, close}, ...].

    Returns None if there are fewer than two points. Otherwise returns the
    polyline points, y-axis gridlines, month labels on the x-axis and the
    per-point positions the hover script uses.
    """
    if not history or len(history) < 2:
        return None
    closes = [p["close"] for p in history]
    low, high = min(closes), max(closes)
    if high == low:
        high, low = high + 1, low - 1
    step = _nice_step(high - low)
    axis_low = math.floor(low / step) * step
    axis_high = math.ceil(high / step) * step

    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    def x_at(i):
        return pad_left + plot_w * i / (len(history) - 1)

    def y_at(v):
        return pad_top + plot_h * (1 - (v - axis_low) / (axis_high - axis_low))

    points = [{"x": round(x_at(i), 1), "y": round(y_at(p["close"]), 1),
               "date": p["date"], "close": p["close"]} for i, p in enumerate(history)]

    gridlines = []
    tick = axis_low
    while tick <= axis_high + step / 1000:
        gridlines.append({"y": round(y_at(tick), 1), "label": f"{tick:,.0f}"})
        tick += step

    # One x label at the first trading day of each month (skipping a cramped first one)
    x_labels, last_month = [], None
    for i, p in enumerate(history):
        month = p["date"][:7]
        if month != last_month:
            if i > 3 or not x_labels:
                label = date.fromisoformat(p["date"]).strftime("%b")
                x_labels.append({"x": round(x_at(i), 1), "label": label})
            last_month = month
    if len(x_labels) > 1 and x_labels[1]["x"] - x_labels[0]["x"] < 30:
        x_labels.pop(0)

    first, last = closes[0], closes[-1]
    return {
        "width": width, "height": height,
        "plot_left": pad_left, "plot_right": width - pad_right,
        "plot_top": pad_top, "plot_bottom": height - pad_bottom,
        "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
        "points": points,
        "gridlines": gridlines,
        "x_labels": x_labels,
        "start_date": history[0]["date"],
        "end_date": history[-1]["date"],
        "change_pct": (last - first) / first * 100 if first else None,
        "low": low, "high": high,
    }


def register(app) -> None:
    """Make the helpers available in templates."""
    app.jinja_env.filters.update(money=money, pct=pct, number=number,
                                 direction=direction)
    app.jinja_env.globals.update(range_position=range_position,
                                 price_chart=price_chart,
                                 currency_symbol=currency_symbol)
