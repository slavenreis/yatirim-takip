"""Yatırım takip dashboard - Flask backend + arka plan güncelleyici."""

import logging
import os
import threading
import time

from flask import Flask, jsonify, send_from_directory

from backfill import run_backfill
from bist30 import BIST30
from commodities import fetch_commodity_quotes
from currencies import fetch_currency_quotes
from db import get_history, get_latest_quotes, init_db, save_quotes
from kap import get_company_kap_data
from metals import fetch_metal_quotes
from prices import fetch_quotes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 15 * 60

app = Flask(__name__, static_folder="../frontend", static_url_path="")


def refresh_all() -> None:
    logger.info("Veri güncelleniyor...")

    try:
        bist_quotes = fetch_quotes(BIST30)
        save_quotes(bist_quotes, "bist30")
        logger.info("BIST30: %d/%d hisse güncellendi", len(bist_quotes), len(BIST30))
    except Exception:
        logger.exception("BIST30 güncellemesi başarısız")

    try:
        metal_quotes = fetch_metal_quotes()
        save_quotes(metal_quotes, "metal")
        logger.info("Metal: %d güncellendi", len(metal_quotes))
    except Exception:
        logger.exception("Metal güncellemesi başarısız")

    try:
        commodity_quotes = fetch_commodity_quotes()
        save_quotes(commodity_quotes, "commodity")
        logger.info("Emtia: %d güncellendi", len(commodity_quotes))
    except Exception:
        logger.exception("Emtia güncellemesi başarısız")

    try:
        currency_quotes = fetch_currency_quotes()
        save_quotes(currency_quotes, "currency")
        logger.info("Döviz: %d güncellendi", len(currency_quotes))
    except Exception:
        logger.exception("Döviz güncellemesi başarısız")

    logger.info("Güncelleme tamamlandı.")


def background_updater() -> None:
    while True:
        try:
            refresh_all()
        except Exception:
            logger.exception("Arka plan güncelleme döngüsünde beklenmeyen hata")
        time.sleep(REFRESH_INTERVAL_SECONDS)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/quotes")
def api_quotes():
    rows = get_latest_quotes()
    data = {"bist30": [], "metal": [], "commodity": [], "currency": []}
    for row in rows:
        item = {
            "ticker": row["ticker"],
            "name": row["name"],
            "price": row["price"],
            "previous_close": row["previous_close"],
            "change_pct": row["change_pct"],
            "currency": row["currency"],
            "price_try": row["price_try"],
            "fetched_at": row["fetched_at"],
        }
        data.setdefault(row["category"], []).append(item)
    return jsonify(data)


@app.route("/api/kap/<ticker>")
def api_kap(ticker):
    """BIST30 hissesi için KAP bildirimleri/temettü/faaliyet raporu bilgisi.

    Sonuçlar kap.py içinde 1 saat önbelleklenir; KAP sayfaları yavaş
    olabileceğinden bu uç nokta yalnızca kullanıcı bir hisse kartına
    tıkladığında (istek üzerine) çağrılır.
    """
    stock_code = ticker.upper().replace(".IS", "")
    data = get_company_kap_data(stock_code)
    if data is None:
        return jsonify({"error": "Bu hisse için KAP eşlemesi bulunamadı"}), 404

    def disclosure_dict(d):
        if d is None:
            return None
        return {
            "publish_date": d.publish_date,
            "title": d.title,
            "summary": d.summary,
            "disclosure_class": d.disclosure_class,
            "url": d.url,
        }

    return jsonify(
        {
            "ticker": data.ticker,
            "kap_url": data.kap_url,
            "disclosures": [disclosure_dict(d) for d in data.disclosures],
            "dividend": disclosure_dict(data.dividend),
            "annual_report": disclosure_dict(data.annual_report),
        }
    )


@app.route("/api/history/<path:ticker>")
def api_history(ticker):
    """Bir ticker için OHLC fiyat geçmişi (mum grafiği için, eskiden yeniye)."""
    rows = get_history(ticker, limit=200)
    points = []
    for row in rows:
        close = row["price_try"] if row["price_try"] is not None else row["price"]
        points.append(
            {
                "t": row["fetched_at"],
                "o": row["open_price"] if row["open_price"] is not None else close,
                "h": row["high_price"] if row["high_price"] is not None else close,
                "l": row["low_price"] if row["low_price"] is not None else close,
                "c": close,
            }
        )
    return jsonify({"ticker": ticker, "points": points})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Manuel yenileme tetikler (senkron çalışır, birkaç saniye sürebilir)."""
    refresh_all()
    return jsonify({"status": "ok"})


def startup() -> None:
    """Veritabanını hazırlar ve arka plan görevlerini başlatır.

    Modül import edilir edilmez (hem yerel `python app.py` hem de üretimde
    waitress/gunicorn app'i import ettiğinde) çalışır; böylece sunucu port'a
    hemen bağlanabilir, ilk fiyat çekimi ve geçmiş veri doldurma arka planda
    devam eder.
    """
    init_db()
    threading.Thread(target=background_updater, daemon=True).start()
    threading.Thread(target=run_backfill, daemon=True).start()


startup()

if __name__ == "__main__":
    is_production = "PORT" in os.environ  # Render vb. platformlar PORT'u kendisi set eder
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0" if is_production else os.environ.get("HOST", "127.0.0.1")
    logger.info("Sunucu başlatılıyor: http://%s:%d", host, port)
    from waitress import serve

    serve(app, host=host, port=port)
