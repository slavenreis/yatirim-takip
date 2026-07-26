"""Grafikler ilk açılışta boş görünmesin diye geçmiş fiyat verisiyle veritabanını
bir kereliğine doldurur. BIST30/metal/emtia için yfinance'in günlük kapanış
geçmişini, döviz için TCMB arşivini kullanır. Zaten yeterli geçmişi olan
ticker'lar atlanır, bu yüzden tekrar tekrar çağrılması güvenlidir.
"""

import logging
from datetime import datetime, timedelta

import yfinance as yf

from bist30 import BIST30
from commodities import COMMODITY_TICKERS
from currencies import CURRENCY_NAMES
from db import count_distinct_days, save_history_rows
from metals import GRAMS_PER_TROY_OUNCE, METAL_TICKERS
from tcmb import _fetch_rates_for_date, get_usd_try

logger = logging.getLogger(__name__)

MIN_DAYS_THRESHOLD = 5  # bu kadar günden az geçmişi olan ticker için backfill uygula


def _backfill_yfinance_daily(ticker, name, category, currency, multiplier=None):
    """multiplier: verilirse (ör. güncel USD/TRY veya USD/TRY/gram katsayısı) o
    günün USD kapanış/açılış/en yüksek/en düşük değerleri bu katsayıyla TL'ye
    çevrilip price_try + open/high/low olarak saklanır (metal/emtia için)."""
    try:
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d")
        closes = hist["Close"].tolist()
        opens = hist["Open"].tolist()
        highs = hist["High"].tolist()
        lows = hist["Low"].tolist()
        dates = hist.index.tolist()
        rows = []
        for i in range(1, len(closes)):
            price = float(closes[i])
            prev = float(closes[i - 1])
            if prev == 0:
                continue
            change_pct = (price - prev) / prev * 100
            ts = int(dates[i].timestamp())
            price_try = round(price * multiplier, 2) if multiplier else None
            o = round(float(opens[i]) * multiplier, 2) if multiplier else float(opens[i])
            h = round(float(highs[i]) * multiplier, 2) if multiplier else float(highs[i])
            l = round(float(lows[i]) * multiplier, 2) if multiplier else float(lows[i])
            rows.append((ticker, name, category, price, prev, change_pct, currency, price_try, o, h, l, ts))
        return rows
    except Exception:
        logger.exception("Geçmiş veri alınamadı: %s", ticker)
        return []


def backfill_bist30():
    rows = []
    for ticker, name in BIST30.items():
        if count_distinct_days(ticker) >= MIN_DAYS_THRESHOLD:
            continue
        rows.extend(_backfill_yfinance_daily(ticker, name, "bist30", "TRY"))
    save_history_rows(rows)
    logger.info("BIST30 geçmiş veri: %d satır eklendi", len(rows))


def backfill_metals():
    usd_try = get_usd_try()
    if not usd_try:
        logger.warning("USD/TRY alınamadı, metal geçmişi doldurulamadı")
        return
    multiplier = usd_try / GRAMS_PER_TROY_OUNCE
    rows = []
    for ticker, name in METAL_TICKERS.items():
        if count_distinct_days(ticker) >= MIN_DAYS_THRESHOLD:
            continue
        rows.extend(_backfill_yfinance_daily(ticker, name, "metal", "TRY", multiplier))
    save_history_rows(rows)
    logger.info("Metal geçmiş veri: %d satır eklendi", len(rows))


def backfill_commodities():
    usd_try = get_usd_try()
    rows = []
    for ticker, name in COMMODITY_TICKERS.items():
        if count_distinct_days(ticker) >= MIN_DAYS_THRESHOLD:
            continue
        rows.extend(_backfill_yfinance_daily(ticker, name, "commodity", "USD", usd_try))
    save_history_rows(rows)
    logger.info("Emtia geçmiş veri: %d satır eklendi", len(rows))


def backfill_currencies(days_back: int = 30):
    tickers = {code + "TRY" for code in CURRENCY_NAMES}
    if all(count_distinct_days(t) >= MIN_DAYS_THRESHOLD for t in tickers):
        return

    daily_rates = []
    seen_dates = set()
    date = datetime.now()
    attempts = 0
    while len(daily_rates) < days_back and attempts < days_back + 15:
        attempts += 1
        date -= timedelta(days=1)
        result = _fetch_rates_for_date(date)
        if result:
            bulletin_date, rates = result
            key = bulletin_date.date()
            if key not in seen_dates:
                seen_dates.add(key)
                daily_rates.append((bulletin_date, rates))

    daily_rates.sort(key=lambda x: x[0])

    rows = []
    for code, name in CURRENCY_NAMES.items():
        ticker = code + "TRY"
        prev = None
        for bulletin_date, rates in daily_rates:
            rate = rates.get(code)
            if rate is None:
                continue
            if prev is not None:
                change_pct = (rate - prev) / prev * 100
                ts = int(bulletin_date.timestamp())
                rows.append((ticker, name, "currency", rate, prev, change_pct, "TRY", None, rate, rate, rate, ts))
            prev = rate
    save_history_rows(rows)
    logger.info("Döviz geçmiş veri: %d satır eklendi", len(rows))


def run_backfill():
    logger.info("Geçmiş veri doldurma başlıyor (bu birkaç dakika sürebilir)...")
    try:
        backfill_bist30()
    except Exception:
        logger.exception("BIST30 backfill başarısız")
    try:
        backfill_metals()
    except Exception:
        logger.exception("Metal backfill başarısız")
    try:
        backfill_commodities()
    except Exception:
        logger.exception("Emtia backfill başarısız")
    try:
        backfill_currencies()
    except Exception:
        logger.exception("Döviz backfill başarısız")
    logger.info("Geçmiş veri doldurma tamamlandı.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from db import init_db

    init_db()
    run_backfill()
