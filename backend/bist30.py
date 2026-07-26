"""BIST30 endeksi bileşenleri.

Not: BIST30 bileşimi Borsa İstanbul tarafından üç ayda bir (Şubat, Mayıs,
Ağustos, Kasım) yeniden belirlenir. Bu liste 2026-07 itibarıyla güncel
kaynaklardan (Midas, İnfo Yatırım) doğrulanmıştır; periyodik olarak kontrol
edilip güncellenmelidir.
"""

# ticker (Yahoo Finance formatı, .IS uzantılı) -> şirket adı
BIST30 = {
    "AEFES.IS": "Anadolu Efes",
    "AKBNK.IS": "Akbank",
    "ASELS.IS": "Aselsan",
    "ASTOR.IS": "Astor Enerji",
    "BIMAS.IS": "BİM Birleşik Mağazalar",
    "DSTKF.IS": "Destek Finans Faktoring",
    "EKGYO.IS": "Emlak Konut GYO",
    "ENKAI.IS": "Enka İnşaat",
    "EREGL.IS": "Ereğli Demir Çelik",
    "FROTO.IS": "Ford Otosan",
    "GARAN.IS": "Garanti BBVA",
    "GUBRF.IS": "Gübre Fabrikaları",
    "ISCTR.IS": "İş Bankası (C)",
    "KCHOL.IS": "Koç Holding",
    "KRDMD.IS": "Kardemir (D)",
    "MGROS.IS": "Migros",
    "PETKM.IS": "Petkim",
    "PGSUS.IS": "Pegasus",
    "SAHOL.IS": "Sabancı Holding",
    "SASA.IS": "Sasa Polyester",
    "SISE.IS": "Şişecam",
    "TAVHL.IS": "TAV Havalimanları",
    "TCELL.IS": "Turkcell",
    "THYAO.IS": "Türk Hava Yolları",
    "TOASO.IS": "Tofaş Oto",
    "TRALT.IS": "Türk Altın İşletmeleri",
    "TTKOM.IS": "Türk Telekom",
    "TUPRS.IS": "Tüpraş",
    "VAKBN.IS": "VakıfBank",
    "YKBNK.IS": "Yapı Kredi Bankası",
}

BIST30_TICKERS = list(BIST30.keys())
