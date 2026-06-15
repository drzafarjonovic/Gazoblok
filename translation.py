"""
Gazoblok Bot - Multilingual Translation Module
Deep Translator + Supabase Cache + In-memory cache + i18n helpers
"""
import asyncio
import time
from typing import Optional, List, Sequence

from aiogram.filters import Filter
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from deep_translator import GoogleTranslator

# Qo'llab-quvvatlanadigan tillar
TILLAR = ["uz", "en", "ru", "ar", "tr", "zh-CN", "de"]

# Til nomlari (UI uchun)
TIL_NOMLARI = {
    "uz": "🇺🇿 O'zbek",
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "ar": "🇸🇦 العربية",
    "tr": "🇹🇷 Türkçe",
    "zh-CN": "🇨🇳 中文",
    "de": "🇩🇪 Deutsch",
}

# Deep Translator til kodlari
DEEP_TRANSLATOR_TIL = {
    "en": "english",
    "ru": "russian",
    "ar": "arabic",
    "tr": "turkish",
    "zh-CN": "chinese (simplified)",
    "de": "german",
}

# ──────────────────────────────────────────────────────────────────────────
# Cache qatlamlari
# ──────────────────────────────────────────────────────────────────────────
# 1. Tarjima cache (xotira): {(original, til): tarjima}
_TARJIMA_CACHE: dict = {}

# 2. Foydalanuvchi tili cache (TTL bilan): {user_id: (til, timestamp)}
#    Bu har bir filtr/handlerda get_user chaqirilishining oldini oladi.
_TIL_CACHE: dict = {}
_TIL_TTL = 5.0  # soniya


def invalidate_til_cache(user_id: int) -> None:
    """Foydalanuvchi tili o'zgarganda cache ni tozalash."""
    _TIL_CACHE.pop(user_id, None)


# ──────────────────────────────────────────────────────────────────────────
# UI katalogi va pre-warm (gibrid: avtomatik tarjima + oldindan cache'lash)
# ──────────────────────────────────────────────────────────────────────────
# Statik UI matnlari (tugmalar va kanonik nomlar) shu yerga avtomatik
# ro'yxatdan o'tadi. Bu lug'at QO'LDA yuritilmaydi — Tkey/eq/canon/
# build_keyboard chaqirilganda o'zidan to'ldiriladi.
_CATALOG: set = set()

# Qaysi til qancha catalog elementi bilan "isitilgan": {til: size}
_WARMED: dict = {}

# Pre-warm uchun bir vaqtning o'zida ortiqcha ish bo'lmasligi uchun lock
_WARM_LOCKS: dict = {}
_WARM_GUARD = asyncio.Lock()

# Pre-warm vaqtida Google'ga bir vaqtda yuboriladigan maksimal so'rovlar
_PREWARM_CONCURRENCY = 8


def register_ui(*uz_texts: str) -> None:
    """Statik UI matnlarini katalogga qo'shadi (pre-warm uchun)."""
    for s in uz_texts:
        if s and s.strip():
            _CATALOG.add(s)


async def prewarm(til: str) -> None:
    """
    Katalogdagi barcha (hali cache'da bo'lmagan) UI matnlarini
    berilgan tilga PARALLEL tarjima qilib, xotira + Supabase cache'ga saqlaydi.
    """
    if til == "uz" or til not in TILLAR:
        return
    targets = [s for s in list(_CATALOG) if (s, til) not in _TARJIMA_CACHE]
    if not targets:
        return

    sem = asyncio.Semaphore(_PREWARM_CONCURRENCY)

    async def _one(s: str):
        async with sem:
            await tarjima_qil(s, til)

    await asyncio.gather(*(_one(s) for s in targets), return_exceptions=True)


async def ensure_warm(til: str) -> None:
    """
    Til hali to'liq isitilmagan bo'lsa, bir marta pre-warm qiladi.
    Tez-tez chaqirilsa ham xavfsiz (isitilgan bo'lsa darhol qaytadi).
    """
    if til == "uz" or til not in TILLAR:
        return
    if _WARMED.get(til, -1) >= len(_CATALOG):
        return
    # Til uchun lock olamiz (ikki marta isitmaslik uchun)
    async with _WARM_GUARD:
        lock = _WARM_LOCKS.setdefault(til, asyncio.Lock())
    async with lock:
        size = len(_CATALOG)
        if _WARMED.get(til, -1) >= size:
            return
        await prewarm(til)
        _WARMED[til] = size


async def tarjima_qil(matn: str, til: str) -> str:
    """
    Matnni berilgan tilga tarjima qilish (xotira + Supabase cache + Google).

    Args:
        matn: Tarjima qilinadigan matn (o'zbekcha)
        til: Maqsad til kodi (uz, en, ru, ar, tr, zh-CN, de)

    Returns:
        Tarjima qilingan matn yoki xatolikda original matn
    """
    # Bo'sh matn tekshiruvi
    if not matn or not matn.strip():
        return matn

    # O'zbek tili uchun tarjima kerak emas
    if til == "uz":
        return matn

    # Til kodini tekshirish
    if til not in TILLAR:
        return matn

    # 0. Xotira cache
    cache_key = (matn, til)
    if cache_key in _TARJIMA_CACHE:
        return _TARJIMA_CACHE[cache_key]

    try:
        # Database dan import (circular import oldini olish uchun ichkarida)
        import database as db

        # 1. Avval Supabase cache dan qidirish
        cached = await db.get_translation(matn, til)
        if cached:
            _TARJIMA_CACHE[cache_key] = cached
            return cached

        # 2. Deep Translator bilan tarjima qilish
        til_nomi = DEEP_TRANSLATOR_TIL.get(til)
        if not til_nomi:
            return matn

        # Sync funksiyani async qilish
        def sync_translate():
            translator = GoogleTranslator(source="auto", target=til_nomi)
            return translator.translate(matn)

        tarjima = await asyncio.to_thread(sync_translate)

        if not tarjima:
            return matn

        # 3. Tarjimani Supabase + xotira ga saqlash (cache)
        await db.save_translation(matn, til, tarjima)
        _TARJIMA_CACHE[cache_key] = tarjima

        return tarjima

    except Exception as e:
        # Xatolikda original matnni qaytarish (fallback)
        print(f"Tarjima xatoligi ({til}): {e}")
        return matn


async def foydalanuvchi_tili(user_id: int) -> str:
    """
    Foydalanuvchi tilini olish (TTL cache bilan).

    Args:
        user_id: Telegram foydalanuvchi ID

    Returns:
        Til kodi (default: "uz")
    """
    now = time.monotonic()
    cached = _TIL_CACHE.get(user_id)
    if cached and (now - cached[1]) < _TIL_TTL:
        return cached[0]

    til = "uz"
    try:
        import database as db
        user = await db.get_user(user_id)
        if user and user.get("til"):
            til = user["til"]
    except Exception:
        til = "uz"

    _TIL_CACHE[user_id] = (til, now)
    return til


async def t(matn: str, user_id: int) -> str:
    """
    Qisqa nom - Matnni foydalanuvchi tiliga tarjima qilish.

    Args:
        matn: Tarjima qilinadigan matn
        user_id: Foydalanuvchi ID

    Returns:
        Tarjima qilingan matn
    """
    til = await foydalanuvchi_tili(user_id)
    return await tarjima_qil(matn, til)


# ──────────────────────────────────────────────────────────────────────────
# i18n yordamchilari (tugma / xabar / klaviatura)
# ──────────────────────────────────────────────────────────────────────────
async def matn_mos(text: str, til: str, uz_text: str) -> bool:
    """Kelgan `text` berilgan kanonik o'zbekcha `uz_text` ga (til bo'yicha) mos keladimi."""
    if til == "uz":
        return text == uz_text
    return text == await tarjima_qil(uz_text, til)


class Tkey(Filter):
    """
    aiogram filtri: xabar matni berilgan kanonik o'zbekcha tugma matniga
    (foydalanuvchi tiliga tarjima qilingan holatda) teng bo'lsa, mos keladi.

    Misol:
        @router.message(Tkey("🏭 Ishlab chiqarish"))
    """

    def __init__(self, *uz_texts: str):
        self.uz_texts = uz_texts
        register_ui(*uz_texts)

    async def __call__(self, message: Message) -> bool:
        if not message.text or not message.from_user:
            return False
        til = await foydalanuvchi_tili(message.from_user.id)
        if til == "uz":
            return message.text in self.uz_texts
        for uz in self.uz_texts:
            if message.text == await tarjima_qil(uz, til):
                return True
        return False


async def eq(message: Message, *uz_texts: str) -> bool:
    """State handlerlari ichida tugma matnini tekshirish (til-aware)."""
    register_ui(*uz_texts)
    if not message.text or not message.from_user:
        return False
    til = await foydalanuvchi_tili(message.from_user.id)
    if til == "uz":
        return message.text in uz_texts
    for uz in uz_texts:
        if message.text == await tarjima_qil(uz, til):
            return True
    return False


async def canon(message: Message, candidates: Sequence[str]) -> Optional[str]:
    """
    Kelgan matnga mos keluvchi kanonik o'zbekcha qiymatni qaytaradi.
    Dict lookup (masalan ROL_MAP) uchun ishlatiladi.

    Returns:
        Mos kelgan kanonik uz matni yoki None.
    """
    register_ui(*candidates)
    if not message.text or not message.from_user:
        return None
    til = await foydalanuvchi_tili(message.from_user.id)
    for uz in candidates:
        expected = uz if til == "uz" else await tarjima_qil(uz, til)
        if message.text == expected:
            return uz
    return None


async def build_keyboard(
    user_id: int,
    rows: List[List[str]],
    resize: bool = True,
    one_time: bool = False,
) -> ReplyKeyboardMarkup:
    """
    Kanonik o'zbekcha tugma matnlaridan iborat klaviaturani
    foydalanuvchi tiliga tarjima qilib quradi.

    Args:
        user_id: Foydalanuvchi ID
        rows: Tugma qatorlari, har bir qator — o'zbekcha matnlar ro'yxati
    """
    for row in rows:
        register_ui(*row)
    til = await foydalanuvchi_tili(user_id)
    keyboard = []
    for row in rows:
        tugmalar = []
        for uz in row:
            matn = uz if til == "uz" else await tarjima_qil(uz, til)
            tugmalar.append(KeyboardButton(text=matn))
        keyboard.append(tugmalar)
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=resize,
        one_time_keyboard=one_time,
    )


async def say(message: Message, text: str, **kwargs):
    """
    Matnni foydalanuvchi tiliga tarjima qilib yuborish.
    reply_markup va boshqa argumentlar to'g'ridan-to'g'ri uzatiladi.
    """
    user_id = message.from_user.id if message.from_user else 0
    tarjima = await t(text, user_id)
    return await message.answer(tarjima, **kwargs)
