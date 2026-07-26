"""SQLite üzerinde fiyat geçmişi saklama katmanı."""

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    previous_close REAL NOT NULL,
    change_pct REAL NOT NULL,
    currency TEXT NOT NULL,
    price_try REAL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    fetched_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_price_history_ticker_time
    ON price_history (ticker, fetched_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_price_history_unique
    ON price_history (ticker, fetched_at);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        for column in ("price_try REAL", "open_price REAL", "high_price REAL", "low_price REAL"):
            try:
                conn.execute(f"ALTER TABLE price_history ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass  # kolon zaten var
        conn.commit()
    finally:
        conn.close()


def save_quotes(quotes: list, category: str) -> None:
    """Quote listesini price_history tablosuna kaydeder.

    Grafik (mum) çizimi open/high/low/close değerlerinin hepsinin dolu
    olmasını gerektirir; kaynaktan biri eksik gelirse (ör. piyasa dışı saatte
    dayHigh/dayLow olmayabilir) o gün için tek nokta olarak fiyatın kendisine
    (doji) düşülür.
    """
    now = int(time.time())
    rows = []
    for q in quotes:
        price_try = getattr(q, "price_try", None)
        close_ref = price_try if price_try is not None else q.price
        rows.append(
            (
                q.ticker,
                q.name,
                category,
                q.price,
                q.previous_close,
                q.change_pct,
                q.currency,
                price_try,
                getattr(q, "open", None) or close_ref,
                getattr(q, "high", None) or close_ref,
                getattr(q, "low", None) or close_ref,
                now,
            )
        )
    save_history_rows(rows)


def save_history_rows(rows: list[tuple]) -> None:
    """(ticker, name, category, price, previous_close, change_pct, currency, price_try,
    open_price, high_price, low_price, fetched_at) tuple'larını toplu olarak kaydeder.
    Aynı (ticker, fetched_at) çiftinde zaten kayıt varsa atlar (backfill ile canlı
    veri çakışmasın diye)."""
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT OR IGNORE INTO price_history
                (ticker, name, category, price, previous_close, change_pct, currency,
                 price_try, open_price, high_price, low_price, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def count_distinct_days(ticker: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT fetched_at / 86400) AS c FROM price_history WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()


def get_latest_quotes(category: str | None = None) -> list[sqlite3.Row]:
    """Her ticker için en son kaydedilen fiyatı döner."""
    conn = get_connection()
    try:
        where = "WHERE category = ?" if category else ""
        params = (category,) if category else ()
        rows = conn.execute(
            f"""
            SELECT ph.*
            FROM price_history ph
            INNER JOIN (
                SELECT ticker, MAX(fetched_at) AS max_time
                FROM price_history
                {where}
                GROUP BY ticker
            ) latest
            ON ph.ticker = latest.ticker AND ph.fetched_at = latest.max_time
            ORDER BY ph.category, ph.name
            """,
            params,
        ).fetchall()
        return rows
    finally:
        conn.close()


def get_history(ticker: str, limit: int = 200) -> list[sqlite3.Row]:
    """Bir ticker için fiyat geçmişini eskiden yeniye sıralı döner (grafik için)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM price_history
                WHERE ticker = ?
                ORDER BY fetched_at DESC
                LIMIT ?
            )
            ORDER BY fetched_at ASC
            """,
            (ticker, limit),
        ).fetchall()
        return rows
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Veritabanı hazır: {DB_PATH}")
