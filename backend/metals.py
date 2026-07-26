"""Altın ve gümüş için ons/gram TL fiyat hesaplama."""

import logging
from dataclasses import dataclass

import yfinance as yf

from tcmb import get_usd_try

logger = logging.getLogger(__name__)

GRAMS_PER_TROY_OUNCE = 31.1034768

# yfinance vadeli işlem tickerları (ons başına USD)
METAL_TICKERS = {
    "GC=F": "Altın",
    "SI=F": "Gümüş",
}


@dataclass
class MetalQuote:
    ticker: str
    name: str
    price: float  # gram TL fiyatı (dashboard'da "price" alanı olarak kullanılacak)
    previous_close: float  # önceki günün gram TL fiyatı
    change_pct: float
    currency: str
    ons_usd: float
    usd_try: float
    open: float | None = None
    high: float | None = None
    low: float | None = None


def fetch_metal_quotes() -> list[MetalQuote]:
    usd_try = get_usd_try()
    if usd_try is None:
        logger.error("USD/TRY kuru alınamadı, metal fiyatları hesaplanamıyor")
        return []

    quotes = []
    for ticker, name in METAL_TICKERS.items():
        try:
            fi = yf.Ticker(ticker).fast_info
            ons_usd = fi.get("lastPrice")
            ons_usd_prev = fi.get("previousClose")
            if ons_usd is None or not ons_usd_prev:
                logger.warning("Eksik veri: %s", ticker)
                continue

            gram_try = ons_usd * usd_try / GRAMS_PER_TROY_OUNCE
            # önceki kapanışı da aynı güncel kur ile yaklaşık hesaplıyoruz
            # (TCMB günlük kur yayınladığı için gün içi kur geçmişi yok)
            gram_try_prev = ons_usd_prev * usd_try / GRAMS_PER_TROY_OUNCE
            change_pct = (gram_try - gram_try_prev) / gram_try_prev * 100

            ons_open = fi.get("open")
            ons_high = fi.get("dayHigh")
            ons_low = fi.get("dayLow")
            multiplier = usd_try / GRAMS_PER_TROY_OUNCE

            quotes.append(
                MetalQuote(
                    ticker=ticker,
                    name=name,
                    price=round(gram_try, 2),
                    previous_close=round(gram_try_prev, 2),
                    change_pct=round(change_pct, 2),
                    currency="TRY",
                    ons_usd=round(ons_usd, 2),
                    usd_try=round(usd_try, 4),
                    open=round(ons_open * multiplier, 2) if ons_open else None,
                    high=round(ons_high * multiplier, 2) if ons_high else None,
                    low=round(ons_low * multiplier, 2) if ons_low else None,
                )
            )
        except Exception:
            logger.exception("Metal fiyatı çekilemedi: %s", ticker)

    return quotes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for q in fetch_metal_quotes():
        sign = "+" if q.change_pct >= 0 else ""
        print(
            f"{q.name:8s} gram={q.price:>9.2f} TRY  ({sign}{q.change_pct:.2f}%)  "
            f"ons={q.ons_usd} USD  usdtry={q.usd_try}"
        )
