"""TCMB (Türkiye Cumhuriyet Merkez Bankası) döviz kuru çekme."""

import logging
from datetime import datetime, timedelta
from xml.etree import ElementTree

import requests

logger = logging.getLogger(__name__)

TODAY_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
ARCHIVE_URL = "https://www.tcmb.gov.tr/kurlar/{yyyymm}/{ddmmyyyy}.xml"


def _parse_bulletin_date(root: ElementTree.Element) -> datetime | None:
    date_str = root.get("Date")  # format: MM/DD/YYYY
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%m/%d/%Y")
    except ValueError:
        return None


def _parse_rates(xml_text: str) -> dict[str, float]:
    """XML içindeki tüm dövizler için alış-satış ortalamasını (1 birim TRY karşılığı) döner.

    TCMB bazı dövizleri (örn. JPY) 100 birim üzerinden yayınlar; Unit alanına
    bölünerek 1 birim karşılığına normalize edilir.
    """
    root = ElementTree.fromstring(xml_text)
    rates = {}
    for currency in root.findall(".//Currency"):
        code = currency.get("Kod")
        selling = currency.findtext("ForexSelling")
        buying = currency.findtext("ForexBuying")
        unit = currency.findtext("Unit")
        if not code or not selling or not buying:
            continue
        try:
            avg = (float(selling) + float(buying)) / 2
            unit_value = float(unit) if unit else 1.0
            rates[code] = avg / unit_value
        except ValueError:
            continue
    return rates


def _fetch_rates_for_date(date: datetime | None) -> tuple[datetime, dict[str, float]] | None:
    url = TODAY_URL if date is None else ARCHIVE_URL.format(
        yyyymm=date.strftime("%Y%m"), ddmmyyyy=date.strftime("%d%m%Y")
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        root = ElementTree.fromstring(r.text)
        rates = _parse_rates(r.text)
        bulletin_date = _parse_bulletin_date(root) or date or datetime.now()
        return (bulletin_date, rates) if rates else None
    except Exception:
        return None


def get_latest_rates(max_days_back: int = 5) -> tuple[datetime, dict[str, float]] | None:
    """En güncel TCMB kurlarını (tüm dövizler) ve gerçek bülten tarihini döner.

    TCMB hafta sonu/tatil günlerinde yayın yapmaz; today.xml başarısız olursa
    (veya hafta sonu nedeniyle son iş gününün verisini tekrar veriyorsa) bu
    fonksiyon XML içindeki gerçek bülten tarihini kullanır, böylece "önceki
    gün" karşılaştırması yanlış güne düşmez.
    """
    result = _fetch_rates_for_date(None)
    if result:
        return result

    logger.warning("TCMB today.xml alınamadı, arşive düşülüyor")
    date = datetime.now()
    for _ in range(max_days_back):
        date -= timedelta(days=1)
        result = _fetch_rates_for_date(date)
        if result:
            return result

    logger.error("TCMB kurları hiçbir kaynaktan alınamadı")
    return None


def get_previous_rates(after_date: datetime, max_days_back: int = 5) -> dict[str, float] | None:
    """Verilen (bülten) tarihinden önceki en yakın iş gününün kurlarını döner."""
    date = after_date
    for _ in range(max_days_back):
        date -= timedelta(days=1)
        result = _fetch_rates_for_date(date)
        if result:
            _, rates = result
            return rates
    return None


def get_usd_try(max_days_back: int = 5) -> float | None:
    """TCMB USD/TRY kurunu döner (alış-satış ortalaması)."""
    result = get_latest_rates(max_days_back)
    if result is None:
        return None
    _, rates = result
    return rates.get("USD")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("USD/TRY:", get_usd_try())
    result = get_latest_rates()
    if result:
        date, rates = result
        print("Tarih:", date.date())
        for code in ("USD", "EUR", "GBP", "CNY", "JPY"):
            print(code, rates.get(code))
