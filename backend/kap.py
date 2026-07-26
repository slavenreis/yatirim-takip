"""KAP (Kamuyu Aydınlatma Platformu, kap.org.tr) bildirim/temettü/faaliyet raporu çekme.

KAP'ın yapısal/genel bir API'si yok; şirket özet sayfası ve bildirim sorgu
sonucu sayfaları Next.js tarafından sunucu taraflı render ediliyor ve veriler
sayfa HTML'i içine gömülü JSON olarak geliyor. Bu modül JS eklemeden, düz bir
HTTP GET ile bu HTML'i çekip embedded JSON'u regex ile ayıklıyor.

Sayfa yapısı KAP tarafından değiştirilirse bu ayıklama bozulabilir; bu yüzden
her adım hataya karşı korumalı ve en kötü ihtimalle sadece şirketin KAP
sayfasına link döndürülür.
"""

import logging
import re
import time
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kap.org.tr"
HEADERS = {"User-Agent": "Mozilla/5.0 (yatirim-takip-dashboard)"}

# BIST30 hisseleri için KAP şirket özet sayfası yolu (companyCode-slug).
# Bu yollar kap.org.tr/tr/bist-sirketler listesinden çıkarılmıştır; şirket
# unvanı/kodu değişmediği sürece kalıcıdır.
KAP_COMPANY_PATHS = {
    "AEFES": "/tr/sirket-bilgileri/ozet/858-anadolu-efes-biracilik-ve-malt-sanayii-a-s",
    "AKBNK": "/tr/sirket-bilgileri/ozet/2413-akbank-t-a-s",
    "ASELS": "/tr/sirket-bilgileri/ozet/866-aselsan-elektronik-sanayi-ve-ticaret-a-s",
    "ASTOR": "/tr/sirket-bilgileri/ozet/4680-astor-enerji-a-s",
    "BIMAS": "/tr/sirket-bilgileri/ozet/1406-bim-birlesik-magazalar-a-s",
    "DSTKF": "/tr/sirket-bilgileri/ozet/2191-destek-finans-faktoring-a-s",
    "EKGYO": "/tr/sirket-bilgileri/ozet/1531-emlak-konut-gayrimenkul-yatirim-ortakligi-a-s",
    "ENKAI": "/tr/sirket-bilgileri/ozet/942-enka-insaat-ve-sanayi-a-s",
    "EREGL": "/tr/sirket-bilgileri/ozet/944-eregli-demir-ve-celik-fabrikalari-t-a-s",
    "FROTO": "/tr/sirket-bilgileri/ozet/956-ford-otomotiv-sanayi-a-s",
    "GARAN": "/tr/sirket-bilgileri/ozet/2422-turkiye-garanti-bankasi-a-s",
    "GUBRF": "/tr/sirket-bilgileri/ozet/974-gubre-fabrikalari-t-a-s",
    "ISCTR": "/tr/sirket-bilgileri/ozet/2425-turkiye-is-bankasi-a-s",
    "KCHOL": "/tr/sirket-bilgileri/ozet/1005-koc-holding-a-s",
    "KRDMD": "/tr/sirket-bilgileri/ozet/994-kardemir-karabuk-demir-celik-sanayi-ve-ticaret-a-s",
    "MGROS": "/tr/sirket-bilgileri/ozet/1494-migros-ticaret-a-s",
    "PETKM": "/tr/sirket-bilgileri/ozet/1053-petkim-petrokimya-holding-a-s",
    "PGSUS": "/tr/sirket-bilgileri/ozet/1710-pegasus-hava-tasimaciligi-a-s",
    "SAHOL": "/tr/sirket-bilgileri/ozet/976-haci-omer-sabanci-holding-a-s",
    "SASA": "/tr/sirket-bilgileri/ozet/1068-sasa-polyester-sanayi-a-s",
    "SISE": "/tr/sirket-bilgileri/ozet/1087-turkiye-sise-ve-cam-fabrikalari-a-s",
    "TAVHL": "/tr/sirket-bilgileri/ozet/1452-tav-havalimanlari-holding-a-s",
    "TCELL": "/tr/sirket-bilgileri/ozet/1103-turkcell-iletisim-hizmetleri-a-s",
    "THYAO": "/tr/sirket-bilgileri/ozet/1107-turk-hava-yollari-a-o",
    "TOASO": "/tr/sirket-bilgileri/ozet/1096-tofas-turk-otomobil-fabrikasi-a-s",
    "TRALT": "/tr/sirket-bilgileri/ozet/1500-turk-altin-isletmeleri-a-s",
    "TTKOM": "/tr/sirket-bilgileri/ozet/1473-turk-telekomunikasyon-a-s",
    "TUPRS": "/tr/sirket-bilgileri/ozet/1105-tupras-turkiye-petrol-rafinerileri-a-s",
    "VAKBN": "/tr/sirket-bilgileri/ozet/2428-turkiye-vakiflar-bankasi-t-a-o",
    "YKBNK": "/tr/sirket-bilgileri/ozet/2429-yapi-ve-kredi-bankasi-a-s",
}

_DISCLOSURE_FIELDS = ("publishDate", "disclosureIndex", "stockCode", "title", "summary", "disclosureClass")
_disclosure_pattern = re.compile(r'\{\\"disclosureBasic\\":\{(.*?)\}\}')


@dataclass
class Disclosure:
    publish_date: str
    index: str
    title: str
    summary: str
    disclosure_class: str
    url: str = field(init=False)

    def __post_init__(self):
        self.url = f"{BASE_URL}/tr/Bildirim/{self.index}"


@dataclass
class KapCompanyData:
    ticker: str
    kap_url: str
    disclosures: list  # list[Disclosure], en güncel ~8 bildirim
    dividend: "Disclosure | None"
    annual_report: "Disclosure | None"


_cache: dict[str, tuple[float, KapCompanyData]] = {}
_CACHE_TTL_SECONDS = 60 * 60  # 1 saat


def _extract_member_oid(summary_html: str) -> str | None:
    idx = summary_html.find("memberDetail")
    if idx == -1:
        return None
    window = summary_html[idx: idx + 1500]
    m = re.search(r'\\"mkkMemberOid\\":\\"([^\\"]+)\\"', window)
    return m.group(1) if m else None


def _clean_text(s: str) -> str:
    s = re.sub(r"\\+[nrt]", " ", s)  # kaçışlı satır sonu/tab kalıntıları (\n, \\n, ...)
    s = s.replace("\\", "")
    return re.sub(r"\s+", " ", s).strip()


def _parse_disclosures(html: str) -> list[Disclosure]:
    results = []
    for m in _disclosure_pattern.finditer(html):
        block = m.group(1).replace('\\"', '"')
        values = {}
        for key in _DISCLOSURE_FIELDS:
            fm = re.search(r'"' + key + r'":"?([^",}]*)"?,?', block)
            values[key] = _clean_text(fm.group(1)) if fm else ""
        if not values.get("disclosureIndex") or values["disclosureIndex"] == "null":
            continue
        results.append(
            Disclosure(
                publish_date=values["publishDate"],
                index=values["disclosureIndex"],
                title=values["title"],
                summary=values["summary"],
                disclosure_class=values["disclosureClass"],
            )
        )
    return results


def _find_first(disclosures: list[Disclosure], predicate) -> "Disclosure | None":
    for d in disclosures:
        if predicate(d):
            return d
    return None


def get_company_kap_data(ticker: str) -> KapCompanyData | None:
    """Bir BIST30 hissesi için KAP linki, son bildirimler, temettü ve faaliyet
    raporu bilgisini döner. KAP_COMPANY_PATHS'te olmayan tickerlar için None."""

    path = KAP_COMPANY_PATHS.get(ticker)
    if path is None:
        return None

    cached = _cache.get(ticker)
    if cached and time.time() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    kap_url = BASE_URL + path
    disclosures: list[Disclosure] = []
    dividend = None
    annual_report = None

    try:
        r = requests.get(kap_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        member_oid = _extract_member_oid(r.text)

        if member_oid:
            r2 = requests.get(
                f"{BASE_URL}/tr/bildirim-sorgu-sonuc",
                params={"member": member_oid},
                headers=HEADERS,
                timeout=15,
            )
            r2.raise_for_status()
            all_disclosures = _parse_disclosures(r2.text)
            disclosures = all_disclosures[:8]

            dividend = _find_first(
                all_disclosures,
                lambda d: "kar pay" in d.title.lower() or "temett" in d.title.lower(),
            )
            annual_report = _find_first(
                all_disclosures, lambda d: "faaliyet raporu" in d.title.lower()
            ) or _find_first(all_disclosures, lambda d: d.disclosure_class == "FR")
    except Exception:
        logger.exception("KAP verisi çekilemedi: %s", ticker)

    data = KapCompanyData(
        ticker=ticker,
        kap_url=kap_url,
        disclosures=disclosures,
        dividend=dividend,
        annual_report=annual_report,
    )
    _cache[ticker] = (time.time(), data)
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = get_company_kap_data("TUPRS")
    print("KAP URL:", data.kap_url)
    print(f"\n{len(data.disclosures)} bildirim:")
    for d in data.disclosures:
        print(f"  [{d.publish_date}] {d.title} -> {d.url}")
    print("\nTemettü:", data.dividend.title if data.dividend else "Bulunamadı")
    print("Faaliyet Raporu:", data.annual_report.title if data.annual_report else "Bulunamadı")
