"""database.settings — bot sozlamalari, tarjimalar keshi, valyuta kurslari."""
import time
from .core import get_pool, _settings_cache, _SETTINGS_TTL


# ── Bot sozlamalari ──
async def get_bot_setting(kalit):
    now = time.monotonic()
    hit = _settings_cache.get(kalit)
    if hit and now - hit[1] < _SETTINGS_TTL:
        return hit[0]
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT qiymat FROM bot_settings WHERE kalit=$1", kalit)
    val = row["qiymat"] if row else None
    _settings_cache[kalit] = (val, now)
    return val


async def set_bot_setting(kalit, qiymat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_settings (kalit, qiymat) VALUES ($1,$2)
            ON CONFLICT (kalit) DO UPDATE SET qiymat=$2
        """, kalit, qiymat)
    _settings_cache[kalit] = (qiymat, time.monotonic())


# ── Multilingual (Translations) ──
async def get_translation(original: str, til: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tarjima FROM translations WHERE original=$1 AND til=$2",
            original, til)
        return row["tarjima"] if row else None


async def save_translation(original: str, til: str, tarjima: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO translations (original, til, tarjima)
            VALUES ($1, $2, $3)
            ON CONFLICT (original, til) DO NOTHING
        """, original, til, tarjima)


# ── Valyuta kurslari (cache) ──
async def get_kurs(kod):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT kurs, vaqt_epoch FROM valyuta_kurslari WHERE kod=$1", kod)
        return dict(row) if row else None


async def set_kurs(kod, kurs):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO valyuta_kurslari (kod, kurs, vaqt_epoch)
            VALUES ($1, $2, $3)
            ON CONFLICT (kod) DO UPDATE SET kurs=$2, vaqt_epoch=$3
        """, kod, float(kurs), time.time())
