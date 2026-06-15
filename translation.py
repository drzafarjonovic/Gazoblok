"""
Gazoblok Bot - Multilingual Translation Module
Deep Translator + Supabase Cache
"""
import asyncio
from typing import Optional
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


async def tarjima_qil(matn: str, til: str) -> str:
    """
    Matnni berilgan tilga tarjima qilish.
    
    Args:
        matn: Tarjima qilinadigan matn (o'zbekcha)
        til: Maqsad til kodi (uz, en, ru, ar, tr, zh-CN, de)
    
    Returns:
        Tarjima qilingan matn yoki xatolikda original matn
    """
    # Bo'sh matn tekshiruvi
    if not matn or not matn.strip():
        return ""
    
    # O'zbek tili uchun tarjima kerak emas
    if til == "uz":
        return matn
    
    # Til kodini tekshirish
    if til not in TILLAR:
        return matn
    
    try:
        # Database dan import (circular import oldini olish uchun ichkarida)
        import database as db
        
        # 1. Avval Supabase cache dan qidirish
        cached = await db.get_translation(matn, til)
        if cached:
            return cached
        
        # 2. Deep Translator bilan tarjima qilish
        til_nomi = DEEP_TRANSLATOR_TIL.get(til)
        if not til_nomi:
            return matn
        
        # Sync funksiyani async qilish
        def sync_translate():
            translator = GoogleTranslator(source='auto', target=til_nomi)
            return translator.translate(matn)
        
        tarjima = await asyncio.to_thread(sync_translate)
        
        # 3. Tarjimani Supabase ga saqlash (cache)
        await db.save_translation(matn, til, tarjima)
        
        return tarjima
        
    except Exception as e:
        # Xatolikda original matnni qaytarish (fallback)
        print(f"Tarjima xatoligi ({til}): {e}")
        return matn


async def foydalanuvchi_tili(user_id: int) -> str:
    """
    Foydalanuvchi tilini olish.
    
    Args:
        user_id: Telegram foydalanuvchi ID
    
    Returns:
        Til kodi (default: "uz")
    """
    try:
        import database as db
        user = await db.get_user(user_id)
        
        if user and user.get("til"):
            return user["til"]
        
        return "uz"  # Default til
        
    except Exception:
        return "uz"


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
