"""Yahoo Finance (yfinance) üzerinden hisse/emtia fiyatı çekme yardımcıları."""

import logging
from dataclasses import dataclass

import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    ticker: str
    name: str
    price: float
    previous_close: float
    change_pct: float
    currency: str
    open: float | None = None
    high: float | None = None
    low: float | None = None


def fetch_quote(ticker: str, name: str) -> Quote | None:
    """Tek bir ticker için güncel fiyat/değişim bilgisini döner. Hata halinde None."""
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.get("lastPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        currency = info.get("currency", "TRY")

        if price is None or prev_close in (None, 0):
            logger.warning("Eksik veri: %s (price=%s, prev_close=%s)", ticker, price, prev_close)
            return None

        change_pct = (price - prev_close) / prev_close * 100
        open_price = info.get("open")
        day_high = info.get("dayHigh")
        day_low = info.get("dayLow")
        return Quote(
            ticker=ticker,
            name=name,
            price=round(float(price), 4),
            previous_close=round(float(prev_close), 4),
            change_pct=round(float(change_pct), 2),
            currency=currency,
            open=round(float(open_price), 4) if open_price else None,
            high=round(float(day_high), 4) if day_high else None,
            low=round(float(day_low), 4) if day_low else None,
        )
    except Exception:
        logger.exception("Fiyat çekilemedi: %s", ticker)
        return None


def fetch_quotes(tickers_with_names: dict[str, str]) -> list[Quote]:
    """Birden fazla ticker için sırayla fiyat çeker, başarısız olanları atlar."""
    quotes = []
    for ticker, name in tickers_with_names.items():
        q = fetch_quote(ticker, name)
        if q is not None:
            quotes.append(q)
    return quotes


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    from bist30 import BIST30

    results = fetch_quotes(BIST30)
    print(f"\n{len(results)}/{len(BIST30)} hisse için fiyat alındı.\n")
    for q in results:
        sign = "+" if q.change_pct >= 0 else ""
        print(f"{q.ticker:12s} {q.name:28s} {q.price:>10.2f} {q.currency}  {sign}{q.change_pct:.2f}%")

    missing = set(BIST30) - {q.ticker for q in results}
    if missing:
        print("\nVeri alınamayan tickerlar:", ", ".join(sorted(missing)), file=sys.stderr)
