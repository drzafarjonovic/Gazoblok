"""
Gazoblok Bot - Valyuta moduli
Asos valyuta: UZS (so'm). Barcha narxlar ichkarida UZS da saqlanadi.
Faol valyuta faqat ko'rsatish/kiritish uchun. Kurslar onlayn olinadi
(open.er-api.com), 6 soat cache qilinadi, xatolikda eski cache yoki
qo'lda kiritilgan kurs ishlatiladi.
"""
import asyncio
import json
import logging
import time
import urllib.request

logger = logging.getLogger("gazobot")

# kod: (nomi, belgi)
VALYUTALAR = {
    "UZS": ("So'm", "so'm"),
    "USD": ("Dollar", "$"),
    "EUR": ("Euro", "€"),
    "RUB": ("Rubl", "₽"),
    "GBP": ("Funt", "£"),
    "CNY": ("Yuan", "¥"),
    "TRY": ("Lira", "₺"),
    "SAR": ("Riyal", "SAR"),
}

ASOS = "UZS"  # ichki saqlash valyutasi

API_URL = "https://open.er-api.com/v6/latest/USD"
KURS_TTL = 6 * 3600  # 6 soat


def belgi(kod: str) -> str:
    return VALYUTALAR.get(kod, ("", kod))[1]


def nomi(kod: str) -> str:
    return VALYUTALAR.get(kod, (kod, kod))[0]


def _sync_fetch():
    """Onlayn kurslarni oladi: {kod: '1 kod necha UZS'}."""
    req = urllib.request.Request(API_URL, headers={"User-Agent": "GazoBot/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    rates = data.get("rates") or {}
    uzs_per_usd = rates.get("UZS")
    if not uzs_per_usd:
        return None
    out = {"UZS": 1.0}
    for kod in VALYUTALAR:
        if kod == "UZS":
            continue
        k = rates.get(kod)
        if k:
            # 1 USD = uzs_per_usd UZS, 1 USD = k <kod>  =>  1 <kod> = uzs_per_usd/k UZS
            out[kod] = uzs_per_usd / k
    return out


async def _refresh_rates():
    """Kurslarni onlayn yangilab, bazaga saqlaydi. Muvaffaqiyatsizda None."""
    import database as db
    try:
        rates = await asyncio.to_thread(_sync_fetch)
    except Exception as e:
        logger.warning("Valyuta kursini olishda xato: %r", e)
        return None
    if not rates:
        return None
    for kod, kurs in rates.items():
        try:
            await db.set_kurs(kod, kurs)
        except Exception as e:
            logger.warning("Kurs saqlashda xato (%s): %r", kod, e)
    return rates


async def get_rate(kod: str):
    """
    1 birlik `kod` necha UZS turishini qaytaradi (UZS uchun 1.0).
    Cache(6s) -> onlayn -> eski cache. Topilmasa None.
    """
    if kod == ASOS:
        return 1.0
    if kod not in VALYUTALAR:
        return None
    import database as db
    row = await db.get_kurs(kod)
    now = time.time()
    if row and (now - row["vaqt_epoch"]) < KURS_TTL:
        return row["kurs"]
    rates = await _refresh_rates()
    if rates and kod in rates:
        return rates[kod]
    if row:  # eskirgan bo'lsa ham — fallback
        return row["kurs"]
    return None


async def get_active():
    """Joriy faol valyuta kodi (default UZS)."""
    import database as db
    return (await db.get_bot_setting("valyuta")) or ASOS


async def uzs_to_active(amount_uzs):
    """
    UZS qiymatni faol valyutaga o'giradi.
    Returns (qiymat, kod). Kurs topilmasa UZS da qaytaradi.
    """
    kod = await get_active()
    if kod == ASOS:
        return amount_uzs, ASOS
    r = await get_rate(kod)
    if not r:
        return amount_uzs, ASOS  # kurs yo'q -> UZS ko'rsatamiz
    return amount_uzs / r, kod


async def active_to_uzs(amount):
    """
    Faol valyutadagi qiymatni UZS ga o'giradi (kiritish uchun).
    Returns UZS qiymat yoki None (kurs topilmasa).
    """
    kod = await get_active()
    if kod == ASOS:
        return amount
    r = await get_rate(kod)
    if not r:
        return None
    return amount * r


def format_pul(amount, kod=ASOS) -> str:
    """Pul summasini formatlash: '1 250 000 so'm', '1 250.50 $'."""
    if amount is None:
        return "—"
    try:
        if kod == "UZS":
            s = f"{round(amount):,}".replace(",", " ")
        else:
            s = f"{amount:,.2f}".replace(",", " ")
    except Exception:
        s = str(amount)
    return f"{s} {belgi(kod)}"


async def format_uzs(amount_uzs) -> str:
    """UZS qiymatni faol valyutaga o'girib, formatlab qaytaradi."""
    qiymat, kod = await uzs_to_active(amount_uzs)
    return format_pul(qiymat, kod)
