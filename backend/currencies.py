"""EUR, USD, GBP, CNY, JPY için TCMB üzerinden TRY karşılığı ve günlük değişim."""

import logging
from dataclasses import dataclass

from tcmb import get_latest_rates, get_previous_rates

logger = logging.getLogger(__name__)

CURRENCY_NAMES = {
    "USD": "ABD Doları",
    "EUR": "Euro",
    "GBP": "İngiliz Sterlini",
    "CNY": "Çin Yuanı",
    "JPY": "Japon Yeni",
}


@dataclass
class CurrencyQuote:
    ticker: str
    name: str
    price: float  # 1 birim dövizin TRY karşılığı
    previous_close: float
    change_pct: float
    currency: str
    open: float | None = None
    high: float | None = None
    low: float | None = None


def fetch_currency_quotes() -> list[CurrencyQuote]:
    latest = get_latest_rates()
    if latest is None:
        logger.error("TCMB kurları alınamadı, döviz bölümü boş dönecek")
        return []

    latest_date, rates = latest
    prev_rates = get_previous_rates(latest_date) or {}

    quotes = []
    for code, name in CURRENCY_NAMES.items():
        price = rates.get(code)
        if price is None:
            logger.warning("Kur bulunamadı: %s", code)
            continue

        prev_price = prev_rates.get(code)
        change_pct = ((price - prev_price) / prev_price * 100) if prev_price else 0.0

        quotes.append(
            CurrencyQuote(
                ticker=f"{code}TRY",
                name=name,
                price=round(price, 4),
                previous_close=round(prev_price, 4) if prev_price else round(price, 4),
                change_pct=round(change_pct, 2),
                currency="TRY",
                open=round(price, 4),
                high=round(price, 4),
                low=round(price, 4),
            )
        )

    return quotes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for q in fetch_currency_quotes():
        sign = "+" if q.change_pct >= 0 else ""
        print(f"{q.name:18s} {q.price:>10.4f} {q.currency}  {sign}{q.change_pct:.2f}%")
