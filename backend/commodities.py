"""Petrol (Brent/WTI), platin, paladyum ve bakır gibi temel emtialar için fiyat çekme."""

import logging
from dataclasses import dataclass

import yfinance as yf

from tcmb import get_usd_try

logger = logging.getLogger(__name__)

# yfinance vadeli işlem tickerları (fiyatlar USD cinsinden)
COMMODITY_TICKERS = {
    "BZ=F": "Brent Petrol",
    "CL=F": "WTI Petrol",
    "PL=F": "Platin",
    "PA=F": "Paladyum",
    "HG=F": "Bakır",
}


@dataclass
class CommodityQuote:
    ticker: str
    name: str
    price: float  # USD fiyatı
    previous_close: float
    change_pct: float
    currency: str
    price_try: float | None  # USD fiyatının TCMB kuruyla TL karşılığı
    usd_try: float | None
    open: float | None = None
    high: float | None = None
    low: float | None = None


def fetch_commodity_quotes() -> list[CommodityQuote]:
    usd_try = get_usd_try()
    if usd_try is None:
        logger.warning("USD/TRY kuru alınamadı, emtia fiyatları TL karşılığı olmadan gösterilecek")

    quotes = []
    for ticker, name in COMMODITY_TICKERS.items():
        try:
            fi = yf.Ticker(ticker).fast_info
            price = fi.get("lastPrice")
            prev_close = fi.get("previousClose") or fi.get("regularMarketPreviousClose")
            currency = fi.get("currency", "USD")

            if price is None or not prev_close:
                logger.warning("Eksik veri: %s", ticker)
                continue

            change_pct = (price - prev_close) / prev_close * 100
            price_try = round(price * usd_try, 2) if usd_try else None
            open_price = fi.get("open")
            day_high = fi.get("dayHigh")
            day_low = fi.get("dayLow")

            quotes.append(
                CommodityQuote(
                    ticker=ticker,
                    name=name,
                    price=round(float(price), 4),
                    previous_close=round(float(prev_close), 4),
                    change_pct=round(float(change_pct), 2),
                    currency=currency,
                    price_try=price_try,
                    usd_try=round(usd_try, 4) if usd_try else None,
                    open=round(float(open_price) * usd_try, 2) if open_price and usd_try else None,
                    high=round(float(day_high) * usd_try, 2) if day_high and usd_try else None,
                    low=round(float(day_low) * usd_try, 2) if day_low and usd_try else None,
                )
            )
        except Exception:
            logger.exception("Emtia fiyatı çekilemedi: %s", ticker)

    return quotes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for q in fetch_commodity_quotes():
        sign = "+" if q.change_pct >= 0 else ""
        try_part = f"  (~{q.price_try:.2f} TRY)" if q.price_try is not None else ""
        print(f"{q.name:14s} {q.price:>10.2f} {q.currency}  {sign}{q.change_pct:.2f}%{try_part}")
