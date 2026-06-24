"""
database.core — umumiy yadro: ulanish puli, xotira keshi, birlik konversiyasi,
rol/permission ta'riflari, sxema yaratish (init_db) va migratsiya.

Bu modul boshqa database.* submodullari uchun asos (state) hisoblanadi.
Pul va kesh holati SHU YERDA yashaydi; submodullar kerakli yordamchilarni
shu modualdan import qiladi.
"""
import asyncpg
import asyncio
import os
import time
from datetime import datetime, timezone, timedelta

DATABASE_URL = os.getenv("DATABASE_URL")

# ── Timezone (GMT+5 Toshkent) ──
TOSHKENT_TZ = timezone(timedelta(hours=5))


def hozirgi_vaqt():
    """GMT+5 bo'yicha hozirgi vaqt (timezone aware)"""
    return datetime.now(TOSHKENT_TZ)


def bugungi_sana():
    """GMT+5 bo'yicha bugungi sana (date object)"""
    return hozirgi_vaqt().date()


# ── Birlik konversiyasi ──
BIRLIK_KG = {
    "kg": 1, "g": 0.001, "gramm": 0.001, "gr": 0.001,
    "mg": 0.000001, "tonna": 1000, "ton": 1000, "t": 1000,
    "quintal": 100, "sentner": 100, "meshok": 50, "qop": 50,
}
BIRLIK_LITR = {
    "litr": 1, "l": 1, "ml": 0.001, "millilitr": 0.001,
    "m3": 1000, "kubometr": 1000, "kub": 1000, "dl": 0.1, "cl": 0.01,
}


def birlikni_asosiyga(miqdor, birlik):
    b = birlik.lower().strip()
    if b in BIRLIK_KG:
        return miqdor * BIRLIK_KG[b], "kg"
    elif b in BIRLIK_LITR:
        return miqdor * BIRLIK_LITR[b], "litr"
    return miqdor, birlik


def asosiydan_birlikga(miqdor_asosiy, birlik):
    b = birlik.lower().strip()
    if b in BIRLIK_KG:
        return miqdor_asosiy / BIRLIK_KG[b]
    elif b in BIRLIK_LITR:
        return miqdor_asosiy / BIRLIK_LITR[b]
    return miqdor_asosiy


def birlik_qollab_quvvatlanadimi(birlik):
    """Birlik tizim tomonidan tan olinadimi (kg yoki litr o'lchamida)."""
    b = (birlik or "").lower().strip()
    return b in BIRLIK_KG or b in BIRLIK_LITR


def birlik_bazasi(birlik):
    """Birlik qaysi o'lchamga tegishli: 'kg', 'litr' yoki None."""
    b = (birlik or "").lower().strip()
    if b in BIRLIK_KG:
        return "kg"
    if b in BIRLIK_LITR:
        return "litr"
    return None


ROLLAR = {
    "superadmin": "Super Admin",
    "direktor": "Direktor",
    "omborchi": "Omborchi",
    "ishchi": "Ishchi",
    "sotuvchi": "Sotuvchi",
    "hisobchi": "Hisobchi",
}

# Huquqlar (operatsion + administrativ)
BARCHA_PERMISSIONLAR = [
    "ishlab_chiqarish_kiritish",
    "ishlab_chiqarish_korish",
    "sotuv_kiritish",
    "sotuv_korish",
    "ombor_kiritish",
    "ombor_korish",
    "tayyor_mahsulot_korish",
    "tayyor_mahsulot_tahrirlash",
    "inventarizatsiya",
    "hisobot_korish",
    "moliya_korish",
    "excel_hisobot",
    "sozlama_boshqaruv",
    "foydalanuvchi_boshqaruv",
]

# Administrativ huquqlar (faqat superadmin tomonidan berilishi mumkin)
ADMIN_PERMISSIONLAR = {"sozlama_boshqaruv", "foydalanuvchi_boshqaruv"}


def _rol(*true_perms):
    d = {p: False for p in BARCHA_PERMISSIONLAR}
    for p in true_perms:
        d[p] = True
    return d


# Standart rol huquqlari
STANDART_ROL_PERMISSIONLAR = {
    "superadmin": {p: True for p in BARCHA_PERMISSIONLAR},
    "direktor": _rol(
        "ishlab_chiqarish_korish", "sotuv_korish", "ombor_korish",
        "tayyor_mahsulot_korish", "hisobot_korish", "moliya_korish", "excel_hisobot",
    ),
    "omborchi": _rol(
        "ishlab_chiqarish_korish", "ombor_kiritish", "ombor_korish",
        "tayyor_mahsulot_korish", "tayyor_mahsulot_tahrirlash",
        "inventarizatsiya", "hisobot_korish",
    ),
    "ishchi": _rol(
        "ishlab_chiqarish_kiritish", "ishlab_chiqarish_korish", "ombor_korish",
    ),
    "sotuvchi": _rol(
        "sotuv_kiritish", "sotuv_korish", "tayyor_mahsulot_korish",
    ),
    "hisobchi": _rol(
        "ishlab_chiqarish_korish", "sotuv_korish", "ombor_korish",
        "tayyor_mahsulot_korish", "hisobot_korish", "moliya_korish", "excel_hisobot",
    ),
}

# ── Connection Pool ──
_pool = None
_pool_lock = None


def _get_pool_lock():
    global _pool_lock
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()
    return _pool_lock


async def get_pool():
    global _pool
    # Tez yo'l (lock'siz)
    if _pool is not None:
        return _pool
    # Sekin yo'l: bir vaqtda faqat bitta pool yaratilishini kafolatlaymiz
    async with _get_pool_lock():
        if _pool is None:
            _pool = await asyncpg.create_pool(
                DATABASE_URL,
                statement_cache_size=0,
                min_size=2,
                max_size=10
            )
    return _pool


async def close_pool():
    """Bot to'xtaganda pool'ni toza yopish."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ════════════════════════════════════════════════════════════════════
# Xotira keshi (har-xabar DB aylanishlarini kamaytirish uchun)
# Bot bitta jarayonda ishlagani uchun bu kesh izchil.
# ════════════════════════════════════════════════════════════════════
_USER_TTL = 20.0
_SETTINGS_TTL = 30.0
_PERM_TTL = 20.0
_TOUCH_INTERVAL = 60.0

_user_cache = {}      # {uid: (user_dict|None, ts)}
_settings_cache = {}  # {kalit: (qiymat|None, ts)}
_perm_cache = {}      # {uid: (perms_dict, ts, rol)}
_touch_ts = {}        # {uid: monotonic}

# Mahsulot/blok/shablon TA'RIFLARI keshi (kamdan-kam o'zgaradi).
# DIQQAT: tayyor mahsulot SONI (finished_goods.qoldiq) bu yerda keshlanMAYDI.
_STRUCT_TTL = 60.0
_struct_cache = {}    # {key: (value, ts)}


def _struct_get(key):
    hit = _struct_cache.get(key)
    if hit and time.monotonic() - hit[1] < _STRUCT_TTL:
        return hit[0]
    return None


def _struct_put(key, val):
    _struct_cache[key] = (val, time.monotonic())


def _invalidate_struct():
    _struct_cache.clear()


def _invalidate_user(uid):
    _user_cache.pop(uid, None)
    _perm_cache.pop(uid, None)


def _invalidate_settings(kalit=None):
    if kalit is None:
        _settings_cache.clear()
    else:
        _settings_cache.pop(kalit, None)


def invalidate_all_caches():
    _user_cache.clear()
    _settings_cache.clear()
    _perm_cache.clear()
    _touch_ts.clear()
    _struct_cache.clear()


# ── Database init ──
async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                ism TEXT NOT NULL,
                username TEXT,
                rol TEXT NOT NULL DEFAULT 'ishchi',
                til TEXT DEFAULT 'uz',
                qoshilgan_vaqt TIMESTAMP DEFAULT NOW(),
                faol BOOLEAN DEFAULT TRUE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id SERIAL PRIMARY KEY,
                nomi TEXT NOT NULL,
                qoldiq REAL DEFAULT 0,
                birlik TEXT NOT NULL,
                asl_birlik TEXT NOT NULL
            )
        """)
        # ── Mahsulot turlari (to'liq dinamik) ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mahsulotlar (
                id SERIAL PRIMARY KEY,
                kod TEXT NOT NULL UNIQUE,
                nomi TEXT NOT NULL,
                emoji TEXT DEFAULT '📦',
                ishchi_haqi DOUBLE PRECISION DEFAULT 0,
                qoshimcha_xarajat DOUBLE PRECISION DEFAULT 0,
                faol BOOLEAN DEFAULT TRUE,
                tartib INTEGER DEFAULT 0
            )
        """)
        # ── Mahsulotning blok turlari ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mahsulot_bloklari (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                kod TEXT NOT NULL,
                nomi TEXT NOT NULL,
                olcham TEXT DEFAULT '',
                qolip_dona DOUBLE PRECISION DEFAULT 0,
                sotuv_narx DOUBLE PRECISION DEFAULT 0,
                tannarx_override DOUBLE PRECISION,
                tartib INTEGER DEFAULT 0,
                UNIQUE(product_id, kod)
            )
        """)
        # ── Shablonlar (data-driven) ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shablonlar (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                kod TEXT NOT NULL,
                nomi TEXT NOT NULL,
                faol BOOLEAN DEFAULT TRUE,
                tartib INTEGER DEFAULT 0,
                UNIQUE(product_id, kod)
            )
        """)
        # ── Shablon chiqimi: 1 qolip qaysi blokdan nechta beradi ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shablon_chiqim (
                id SERIAL PRIMARY KEY,
                shablon_id INTEGER NOT NULL,
                block_kod TEXT NOT NULL,
                soni INTEGER NOT NULL,
                UNIQUE(shablon_id, block_kod)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS qolip_formula (
                id SERIAL PRIMARY KEY,
                material_id INTEGER,
                miqdor REAL NOT NULL,
                birlik TEXT NOT NULL,
                miqdor_asosiy REAL NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS production_log (
                id SERIAL PRIMARY KEY,
                sana TEXT NOT NULL,
                shablon INTEGER,
                qolip_soni INTEGER NOT NULL,
                user_id BIGINT,
                vaqt TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sales_log (
                id SERIAL PRIMARY KEY,
                sana TEXT NOT NULL,
                block_type TEXT NOT NULL,
                miqdor INTEGER NOT NULL,
                user_id BIGINT,
                vaqt TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finished_goods (
                id SERIAL PRIMARY KEY,
                block_type TEXT NOT NULL,
                qoldiq INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                id SERIAL PRIMARY KEY,
                kalit TEXT NOT NULL UNIQUE,
                qiymat TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id SERIAL PRIMARY KEY,
                material_id INTEGER UNIQUE,
                min_chegara REAL NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                ism TEXT,
                rol TEXT,
                amal TEXT NOT NULL,
                tafsilot TEXT,
                vaqt TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rol_permissions (
                id SERIAL PRIMARY KEY,
                rol TEXT NOT NULL,
                permission TEXT NOT NULL,
                ruxsat BOOLEAN DEFAULT FALSE,
                UNIQUE(rol, permission)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                permission TEXT NOT NULL,
                ruxsat BOOLEAN DEFAULT FALSE,
                UNIQUE(user_id, permission)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS material_chiqim_log (
                id SERIAL PRIMARY KEY,
                production_log_id INTEGER,
                material_id INTEGER,
                material_nomi TEXT,
                ketgan_miqdor REAL,
                birlik TEXT,
                sana TEXT,
                vaqt TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inventarizatsiya (
                id SERIAL PRIMARY KEY,
                sana TEXT NOT NULL,
                block_type TEXT NOT NULL,
                bot_hisob INTEGER,
                real_hisob INTEGER,
                farq INTEGER,
                izoh TEXT,
                user_id BIGINT,
                vaqt TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                id SERIAL PRIMARY KEY,
                original TEXT NOT NULL,
                til TEXT NOT NULL,
                tarjima TEXT NOT NULL,
                UNIQUE(original, til)
            )
        """)
        # Standart rol permissionlarini yuklash
        for rol, permissionlar in STANDART_ROL_PERMISSIONLAR.items():
            for permission, ruxsat in permissionlar.items():
                await conn.execute("""
                    INSERT INTO rol_permissions (rol, permission, ruxsat)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (rol, permission) DO NOTHING
                """, rol, permission, ruxsat)

        # ── Migratsiya (eski o'rnatishlar uchun, idempotent) ──
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS til TEXT DEFAULT 'uz'"
        )
        await conn.execute(
            "ALTER TABLE materials ADD COLUMN IF NOT EXISTS narx DOUBLE PRECISION DEFAULT 0"
        )
        await conn.execute(
            "ALTER TABLE sales_log ADD COLUMN IF NOT EXISTS narx DOUBLE PRECISION DEFAULT 0"
        )
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS oxirgi_faollik TIMESTAMP"
        )
        # ── Dinamik mahsulot uchun product_id / shablon_id ustunlari ──
        for tbl in ("qolip_formula", "production_log", "sales_log",
                    "finished_goods", "inventarizatsiya", "material_chiqim_log"):
            await conn.execute(
                f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS product_id INTEGER"
            )
        await conn.execute(
            "ALTER TABLE production_log ADD COLUMN IF NOT EXISTS shablon_id INTEGER"
        )
        # Eski production_log.shablon NOT NULL bo'lishi mumkin — bo'shatamiz
        await conn.execute(
            "ALTER TABLE production_log ALTER COLUMN shablon DROP NOT NULL"
        )
        # finished_goods: eski global UNIQUE(block_type) -> (product_id, block_type)
        await conn.execute(
            "ALTER TABLE finished_goods DROP CONSTRAINT IF EXISTS finished_goods_block_type_key"
        )
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS finished_goods_prod_block_uidx "
            "ON finished_goods(product_id, block_type)"
        )

        # Valyuta kurslari cache
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS valyuta_kurslari (
                kod TEXT PRIMARY KEY,
                kurs DOUBLE PRECISION NOT NULL,
                vaqt_epoch DOUBLE PRECISION NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS hisobot_obunachilar (
                user_id BIGINT PRIMARY KEY,
                vaqt TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_users (
                user_id BIGINT PRIMARY KEY,
                ism TEXT,
                username TEXT,
                vaqt TIMESTAMP DEFAULT NOW()
            )
        """)
        # PIN qulf holati (restartdan keyin ham saqlanadi): oxirgi faollik epoch
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pin_holat (
                user_id BIGINT PRIMARY KEY,
                last_active DOUBLE PRECISION NOT NULL
            )
        """)

        # ── Indekslar (hisobot/sana so'rovlarini tezlashtirish, idempotent) ──
        for idx_sql in (
            "CREATE INDEX IF NOT EXISTS idx_prod_prod_sana ON production_log(product_id, sana)",
            "CREATE INDEX IF NOT EXISTS idx_prod_sana ON production_log(sana)",
            "CREATE INDEX IF NOT EXISTS idx_sales_prod_sana ON sales_log(product_id, sana)",
            "CREATE INDEX IF NOT EXISTS idx_sales_sana ON sales_log(sana)",
            "CREATE INDEX IF NOT EXISTS idx_chiqim_sana ON material_chiqim_log(sana)",
            "CREATE INDEX IF NOT EXISTS idx_chiqim_prodlog ON material_chiqim_log(production_log_id)",
            "CREATE INDEX IF NOT EXISTS idx_chiqim_prod ON material_chiqim_log(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_qolip_prod ON qolip_formula(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_bloklar_prod ON mahsulot_bloklari(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_shablon_prod ON shablonlar(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_shchiqim_sh ON shablon_chiqim(shablon_id)",
            "CREATE INDEX IF NOT EXISTS idx_inv_prod ON inventarizatsiya(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_userperm_uid ON user_permissions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_vaqt ON audit_log(vaqt)",
        ):
            await conn.execute(idx_sql)

        # Eski gazoblok ma'lumotlarini dinamik modelga ko'chirish
        await _migrate_to_dynamic(conn)


async def _setting(conn, kalit):
    return await conn.fetchval(
        "SELECT qiymat FROM bot_settings WHERE kalit=$1", kalit
    )


async def _migrate_to_dynamic(conn):
    """
    Eski (gazoblok) ma'lumotlarni dinamik mahsulot modeliga bir martalik
    ko'chiradi. Idempotent: ortib qolgan NULL product_id yozuvlar bo'lsagina
    'gazoblok' mahsulotini yaratib, hammasini unga bog'laydi.
    """
    legacy = await conn.fetchval("""
        SELECT (
            EXISTS(SELECT 1 FROM finished_goods WHERE product_id IS NULL)
            OR EXISTS(SELECT 1 FROM qolip_formula WHERE product_id IS NULL)
            OR EXISTS(SELECT 1 FROM production_log WHERE product_id IS NULL)
            OR EXISTS(SELECT 1 FROM sales_log WHERE product_id IS NULL)
            OR EXISTS(SELECT 1 FROM inventarizatsiya WHERE product_id IS NULL)
        )
    """)
    if not legacy:
        return

    gid = await conn.fetchval("SELECT id FROM mahsulotlar WHERE kod='gazoblok'")
    if gid is None:
        ishchi = float(await _setting(conn, "ishchi_haqi_qolip") or 0)
        qoshimcha = float(await _setting(conn, "qoshimcha_xarajat_qolip") or 0)
        gid = await conn.fetchval(
            "INSERT INTO mahsulotlar (kod, nomi, emoji, ishchi_haqi, qoshimcha_xarajat, tartib) "
            "VALUES ('gazoblok', 'Gazoblok', '🧱', $1, $2, 1) RETURNING id",
            ishchi, qoshimcha
        )

    async def ensure_block(kod, nomi, olcham, qolip_dona, narx_kalit, over_kalit, tartib):
        bid = await conn.fetchval(
            "SELECT id FROM mahsulot_bloklari WHERE product_id=$1 AND kod=$2", gid, kod
        )
        if bid is None:
            narx = float(await _setting(conn, narx_kalit) or 0)
            over_raw = await _setting(conn, over_kalit)
            over = float(over_raw) if over_raw not in (None, "") else None
            await conn.execute(
                "INSERT INTO mahsulot_bloklari "
                "(product_id, kod, nomi, olcham, qolip_dona, sotuv_narx, tannarx_override, tartib) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                gid, kod, nomi, olcham, qolip_dona, narx, over, tartib
            )

    await ensure_block("A", "A blok (60×20×30)", "60×20×30", 12,
                       "sotuv_narx_A", "tannarx_override_A", 1)
    await ensure_block("B", "B blok (60×10×30)", "60×10×30", 24,
                       "sotuv_narx_B", "tannarx_override_B", 2)

    async def ensure_shablon(kod, nomi, chiqim, tartib):
        sid = await conn.fetchval(
            "SELECT id FROM shablonlar WHERE product_id=$1 AND kod=$2", gid, kod
        )
        if sid is None:
            sid = await conn.fetchval(
                "INSERT INTO shablonlar (product_id, kod, nomi, tartib) "
                "VALUES ($1,$2,$3,$4) RETURNING id",
                gid, kod, nomi, tartib
            )
            for bk, soni in chiqim:
                await conn.execute(
                    "INSERT INTO shablon_chiqim (shablon_id, block_kod, soni) "
                    "VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
                    sid, bk, soni
                )
        return sid

    s1 = await ensure_shablon("1", "Shablon 1 — 12A", [("A", 12)], 1)
    s2 = await ensure_shablon("2", "Shablon 2 — 24B", [("B", 24)], 2)
    s3 = await ensure_shablon("3", "Shablon 3 — 11A+2B", [("A", 11), ("B", 2)], 3)

    # Barcha eski yozuvlarni gazoblokka bog'laymiz
    for tbl in ("finished_goods", "qolip_formula", "production_log",
                "sales_log", "inventarizatsiya", "material_chiqim_log"):
        await conn.execute(
            f"UPDATE {tbl} SET product_id=$1 WHERE product_id IS NULL", gid
        )
    # Eski integer shablon -> shablon_id
    await conn.execute(
        "UPDATE production_log SET shablon_id=$1 "
        "WHERE product_id=$2 AND shablon=1 AND shablon_id IS NULL", s1, gid)
    await conn.execute(
        "UPDATE production_log SET shablon_id=$1 "
        "WHERE product_id=$2 AND shablon=2 AND shablon_id IS NULL", s2, gid)
    await conn.execute(
        "UPDATE production_log SET shablon_id=$1 "
        "WHERE product_id=$2 AND shablon=3 AND shablon_id IS NULL", s3, gid)
