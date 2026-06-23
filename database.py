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



# ── Permissions ──
async def get_user_permissions(user_id, rol):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rol_rows = await conn.fetch(
            "SELECT permission, ruxsat FROM rol_permissions WHERE rol=$1", rol
        )
        perms = {r["permission"]: r["ruxsat"] for r in rol_rows}
        user_rows = await conn.fetch(
            "SELECT permission, ruxsat FROM user_permissions WHERE user_id=$1", user_id
        )
        for r in user_rows:
            perms[r["permission"]] = r["ruxsat"]
        return perms

async def get_rol_permissions(rol):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT permission, ruxsat FROM rol_permissions WHERE rol=$1", rol
        )
        return {r["permission"]: r["ruxsat"] for r in rows}

async def set_rol_permission(rol, permission, ruxsat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO rol_permissions (rol, permission, ruxsat)
            VALUES ($1, $2, $3)
            ON CONFLICT (rol, permission) DO UPDATE SET ruxsat=$3
        """, rol, permission, ruxsat)

async def get_user_individual_permissions(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT permission, ruxsat FROM user_permissions WHERE user_id=$1", user_id
        )
        return {r["permission"]: r["ruxsat"] for r in rows}

async def set_user_permission(user_id, permission, ruxsat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_permissions (user_id, permission, ruxsat)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, permission) DO UPDATE SET ruxsat=$3
        """, user_id, permission, ruxsat)

async def clear_user_permissions(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_permissions WHERE user_id=$1", user_id
        )

async def has_permission(user_id, rol, permission):
    perms = await get_user_permissions(user_id, rol)
    return perms.get(permission, False)

# ── Foydalanuvchilar ──
async def get_user(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id=$1 AND faol=TRUE", user_id
        )
        return dict(row) if row else None

async def add_user(user_id, ism, username, rol):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (id, ism, username, rol)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE
            SET ism=$2, username=$3, rol=$4, faol=TRUE
        """, user_id, ism, username, rol)

async def get_all_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM users ORDER BY qoshilgan_vaqt DESC"
        )
        return [dict(r) for r in rows]

async def update_user_rol(user_id, rol):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET rol=$1 WHERE id=$2", rol, user_id
        )

async def delete_user(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET faol=FALSE WHERE id=$1", user_id
        )

async def superadmin_bormi():
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE rol='superadmin' AND faol=TRUE"
        )
        return row is not None

# ── Audit log ──
async def add_audit_log(user_id, ism, rol, amal, tafsilot=""):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO audit_log (user_id, ism, rol, amal, tafsilot)
            VALUES ($1, $2, $3, $4, $5)
        """, user_id, ism, rol, amal, tafsilot)

async def get_audit_log(limit=50):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM audit_log ORDER BY vaqt DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]

# ── Materiallar (umumiy ombor) ──
async def get_materials():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, nomi, qoldiq, birlik, asl_birlik FROM materials ORDER BY id"
        )
        return [tuple(r) for r in rows]

async def add_material(nomi, qoldiq, birlik):
    qoldiq_asosiy, asosiy_birlik = birlikni_asosiyga(qoldiq, birlik)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO materials (nomi, qoldiq, birlik, asl_birlik) VALUES ($1,$2,$3,$4)",
            nomi, qoldiq_asosiy, asosiy_birlik, birlik
        )

async def update_material_qoldiq(material_id, yangi_qoldiq):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE materials SET qoldiq=$1 WHERE id=$2",
            yangi_qoldiq, material_id
        )

async def update_material(material_id, nomi, qoldiq, birlik):
    qoldiq_asosiy, asosiy_birlik = birlikni_asosiyga(qoldiq, birlik)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE materials SET nomi=$1,qoldiq=$2,birlik=$3,asl_birlik=$4 WHERE id=$5",
            nomi, qoldiq_asosiy, asosiy_birlik, birlik, material_id
        )

async def delete_material(material_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM qolip_formula WHERE material_id=$1", material_id)
        await conn.execute("DELETE FROM settings WHERE material_id=$1", material_id)
        await conn.execute("DELETE FROM materials WHERE id=$1", material_id)

async def clear_all_data():
    """Tranzaksion ma'lumotlarni tozalaydi (mahsulot/blok/shablon ta'riflari saqlanadi)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM material_chiqim_log")
        await conn.execute("DELETE FROM audit_log")
        await conn.execute("DELETE FROM sales_log")
        await conn.execute("DELETE FROM production_log")
        await conn.execute("DELETE FROM inventarizatsiya")
        await conn.execute("DELETE FROM settings")
        await conn.execute("DELETE FROM qolip_formula")
        await conn.execute("DELETE FROM materials")
        await conn.execute("UPDATE finished_goods SET qoldiq=0")



# ════════════════════════════════════════════════════════════════════
# MAHSULOTLAR (dinamik)
# ════════════════════════════════════════════════════════════════════
async def get_mahsulotlar(faqat_faol=True):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if faqat_faol:
            rows = await conn.fetch(
                "SELECT * FROM mahsulotlar WHERE faol=TRUE ORDER BY tartib, id")
        else:
            rows = await conn.fetch("SELECT * FROM mahsulotlar ORDER BY tartib, id")
        return [dict(r) for r in rows]

async def get_mahsulot(product_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM mahsulotlar WHERE id=$1", product_id)
        return dict(row) if row else None

async def get_mahsulot_by_kod(kod):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM mahsulotlar WHERE kod=$1", kod)
        return dict(row) if row else None

async def add_mahsulot(kod, nomi, emoji="📦"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        tartib = await conn.fetchval(
            "SELECT COALESCE(MAX(tartib),0)+1 FROM mahsulotlar") or 1
        return await conn.fetchval(
            "INSERT INTO mahsulotlar (kod, nomi, emoji, tartib) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            kod, nomi, emoji, tartib
        )

async def update_mahsulot(product_id, nomi, emoji):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulotlar SET nomi=$1, emoji=$2 WHERE id=$3",
            nomi, emoji, product_id
        )

async def set_mahsulot_ishchi_haqi(product_id, qiymat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulotlar SET ishchi_haqi=$1 WHERE id=$2",
            float(qiymat), product_id
        )

async def set_mahsulot_qoshimcha(product_id, qiymat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulotlar SET qoshimcha_xarajat=$1 WHERE id=$2",
            float(qiymat), product_id
        )

async def set_mahsulot_faol(product_id, faol):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulotlar SET faol=$1 WHERE id=$2", bool(faol), product_id
        )

async def delete_mahsulot(product_id):
    """Arxivlash (soft-delete) — tarix saqlanadi."""
    await set_mahsulot_faol(product_id, False)


# ════════════════════════════════════════════════════════════════════
# MAHSULOT BLOKLARI
# ════════════════════════════════════════════════════════════════════
async def get_bloklar(product_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM mahsulot_bloklari WHERE product_id=$1 ORDER BY tartib, id",
            product_id
        )
        return [dict(r) for r in rows]

async def get_blok(product_id, kod):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mahsulot_bloklari WHERE product_id=$1 AND kod=$2",
            product_id, kod
        )
        return dict(row) if row else None

async def get_blok_by_id(blok_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mahsulot_bloklari WHERE id=$1", blok_id)
        return dict(row) if row else None

async def add_blok(product_id, kod, nomi, olcham, qolip_dona, sotuv_narx=0):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            tartib = await conn.fetchval(
                "SELECT COALESCE(MAX(tartib),0)+1 FROM mahsulot_bloklari WHERE product_id=$1",
                product_id) or 1
            bid = await conn.fetchval(
                "INSERT INTO mahsulot_bloklari "
                "(product_id, kod, nomi, olcham, qolip_dona, sotuv_narx, tartib) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id",
                product_id, kod, nomi, olcham, float(qolip_dona),
                float(sotuv_narx), tartib
            )
            # Tayyor mahsulot qatorini yaratamiz
            await conn.execute(
                "INSERT INTO finished_goods (product_id, block_type, qoldiq) "
                "VALUES ($1,$2,0) ON CONFLICT (product_id, block_type) DO NOTHING",
                product_id, kod
            )
            return bid

async def update_blok(blok_id, nomi, olcham, qolip_dona):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulot_bloklari SET nomi=$1, olcham=$2, qolip_dona=$3 WHERE id=$4",
            nomi, olcham, float(qolip_dona), blok_id
        )

async def set_blok_sotuv_narx(blok_id, narx):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulot_bloklari SET sotuv_narx=$1 WHERE id=$2",
            float(narx), blok_id
        )

async def set_blok_override(blok_id, qiymat):
    """qiymat None bo'lsa override o'chadi (avtomatga qaytadi)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if qiymat is None:
            await conn.execute(
                "UPDATE mahsulot_bloklari SET tannarx_override=NULL WHERE id=$1", blok_id)
        else:
            await conn.execute(
                "UPDATE mahsulot_bloklari SET tannarx_override=$1 WHERE id=$2",
                float(qiymat), blok_id)

async def delete_blok(blok_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT product_id, kod FROM mahsulot_bloklari WHERE id=$1", blok_id)
            if not row:
                return
            pid, kod = row["product_id"], row["kod"]
            # Shu mahsulot shablonlaridagi chiqim qatorlarini olib tashlaymiz
            await conn.execute(
                "DELETE FROM shablon_chiqim WHERE block_kod=$1 AND shablon_id IN "
                "(SELECT id FROM shablonlar WHERE product_id=$2)", kod, pid)
            await conn.execute(
                "DELETE FROM finished_goods WHERE product_id=$1 AND block_type=$2", pid, kod)
            await conn.execute(
                "DELETE FROM mahsulot_bloklari WHERE id=$1", blok_id)


# ════════════════════════════════════════════════════════════════════
# SHABLONLAR
# ════════════════════════════════════════════════════════════════════
async def get_shablonlar(product_id, faqat_faol=False):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if faqat_faol:
            rows = await conn.fetch(
                "SELECT * FROM shablonlar WHERE product_id=$1 AND faol=TRUE ORDER BY tartib, id",
                product_id)
        else:
            rows = await conn.fetch(
                "SELECT * FROM shablonlar WHERE product_id=$1 ORDER BY tartib, id",
                product_id)
        natija = []
        for r in rows:
            chiqim = await conn.fetch(
                "SELECT sc.block_kod, sc.soni, b.nomi AS blok_nomi "
                "FROM shablon_chiqim sc "
                "LEFT JOIN mahsulot_bloklari b "
                "  ON b.product_id=$1 AND b.kod=sc.block_kod "
                "WHERE sc.shablon_id=$2 ORDER BY sc.id",
                product_id, r["id"])
            d = dict(r)
            d["chiqim"] = [dict(c) for c in chiqim]
            natija.append(d)
        return natija

async def get_shablon(shablon_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM shablonlar WHERE id=$1", shablon_id)
        if not row:
            return None
        d = dict(row)
        chiqim = await conn.fetch(
            "SELECT block_kod, soni FROM shablon_chiqim WHERE shablon_id=$1 ORDER BY id",
            shablon_id)
        d["chiqim"] = [dict(c) for c in chiqim]
        return d

async def add_shablon(product_id, kod, nomi):
    pool = await get_pool()
    async with pool.acquire() as conn:
        tartib = await conn.fetchval(
            "SELECT COALESCE(MAX(tartib),0)+1 FROM shablonlar WHERE product_id=$1",
            product_id) or 1
        return await conn.fetchval(
            "INSERT INTO shablonlar (product_id, kod, nomi, tartib) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            product_id, kod, nomi, tartib
        )

async def set_shablon_chiqim(shablon_id, chiqim):
    """chiqim: [(block_kod, soni), ...] — eski chiqimni almashtiradi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM shablon_chiqim WHERE shablon_id=$1", shablon_id)
            for bk, soni in chiqim:
                await conn.execute(
                    "INSERT INTO shablon_chiqim (shablon_id, block_kod, soni) "
                    "VALUES ($1,$2,$3) ON CONFLICT (shablon_id, block_kod) "
                    "DO UPDATE SET soni=$3",
                    shablon_id, bk, int(soni))

async def delete_shablon(shablon_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM shablon_chiqim WHERE shablon_id=$1", shablon_id)
            await conn.execute("DELETE FROM shablonlar WHERE id=$1", shablon_id)


# ════════════════════════════════════════════════════════════════════
# TAYYOR MAHSULOT (product-aware)
# ════════════════════════════════════════════════════════════════════
async def get_finished_goods(product_id):
    """[{kod, nomi, olcham, qoldiq}] — blok tartibi bo'yicha."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT b.kod, b.nomi, b.olcham,
                   COALESCE(f.qoldiq, 0) AS qoldiq
            FROM mahsulot_bloklari b
            LEFT JOIN finished_goods f
                ON f.product_id=b.product_id AND f.block_type=b.kod
            WHERE b.product_id=$1
            ORDER BY b.tartib, b.id
        """, product_id)
        return [dict(r) for r in rows]

async def get_all_finished_goods():
    """Barcha faol mahsulotlar bo'yicha: [{product_id, product_nomi, kod, nomi, qoldiq}]."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.id AS product_id, m.nomi AS product_nomi, m.emoji,
                   b.kod, b.nomi, COALESCE(f.qoldiq,0) AS qoldiq
            FROM mahsulotlar m
            JOIN mahsulot_bloklari b ON b.product_id=m.id
            LEFT JOIN finished_goods f
                ON f.product_id=b.product_id AND f.block_type=b.kod
            WHERE m.faol=TRUE
            ORDER BY m.tartib, m.id, b.tartib, b.id
        """)
        return [dict(r) for r in rows]

async def set_finished_goods(product_id, block_kod, qoldiq):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO finished_goods (product_id, block_type, qoldiq)
            VALUES ($1,$2,$3)
            ON CONFLICT (product_id, block_type) DO UPDATE SET qoldiq=$3
        """, product_id, block_kod, qoldiq)

async def update_finished_goods(product_id, block_kod, delta):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO finished_goods (product_id, block_type, qoldiq)
            VALUES ($1,$2,GREATEST(0,$3))
            ON CONFLICT (product_id, block_type)
            DO UPDATE SET qoldiq=GREATEST(0, finished_goods.qoldiq + $3)
        """, product_id, block_kod, delta)



# ════════════════════════════════════════════════════════════════════
# QOLIP FORMULASI (product-aware)
# ════════════════════════════════════════════════════════════════════
async def get_qolip_formula(product_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.nomi, q.miqdor, q.birlik, m.qoldiq, m.birlik,
                   m.id, q.miqdor_asosiy, m.asl_birlik
            FROM qolip_formula q
            JOIN materials m ON q.material_id = m.id
            WHERE q.product_id=$1
        """, product_id)
        return [tuple(r) for r in rows]

async def add_qolip_formula(product_id, material_id, miqdor, birlik):
    miqdor_asosiy, _ = birlikni_asosiyga(miqdor, birlik)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO qolip_formula (product_id, material_id, miqdor, birlik, miqdor_asosiy) "
            "VALUES ($1,$2,$3,$4,$5)",
            product_id, material_id, miqdor, birlik, miqdor_asosiy
        )

async def clear_qolip_formula(product_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM qolip_formula WHERE product_id=$1", product_id)

async def check_material_yetarli(product_id, jami_qolip):
    formula = await get_qolip_formula(product_id)
    if not formula:
        return ["❌ Qolip formulasi kiritilmagan!"]
    yetishmaydi = []
    for f in formula:
        nomi = f[0]
        miqdor_asosiy = f[6]
        qoldiq_asosiy = f[3]
        asl_birlik = f[7]
        kerak = miqdor_asosiy * jami_qolip
        if qoldiq_asosiy < kerak:
            bor = asosiydan_birlikga(qoldiq_asosiy, asl_birlik)
            kerak_asl = asosiydan_birlikga(kerak, asl_birlik)
            yetishmaydi.append(
                f"❌ {nomi}: kerak {kerak_asl:.2f} {asl_birlik}, "
                f"bor {bor:.2f} {asl_birlik}"
            )
    return yetishmaydi


# ════════════════════════════════════════════════════════════════════
# ISHLAB CHIQARISH (product-aware, atomik)
# ════════════════════════════════════════════════════════════════════
async def _shablon_bloklari(conn, shablon_id, qolip_soni):
    """shablon_chiqim asosida {block_kod: soni} qaytaradi."""
    rows = await conn.fetch(
        "SELECT block_kod, soni FROM shablon_chiqim WHERE shablon_id=$1", shablon_id)
    return {r["block_kod"]: r["soni"] * qolip_soni for r in rows}


async def add_production(product_id, kiritilganlar: dict, user_id):
    """
    Ishlab chiqarishni TO'LIQ atomik tranzaksiyada kiritadi.

    Args:
        product_id: qaysi mahsulot
        kiritilganlar: {shablon_id: qolip_soni}
        user_id: kim kiritmoqda

    Returns:
        (True, payload) yoki (False, {...sabab}).
    """
    kiritilganlar = {int(k): int(v) for k, v in kiritilganlar.items() if int(v) > 0}
    jami_qolip = sum(kiritilganlar.values())
    if jami_qolip <= 0:
        return False, {"bosh": True}

    bugun = bugungi_sana()
    sana_str = bugun.isoformat()

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Blok chiqimini hisoblaymiz
            blok_jami = {}
            shablon_satrlar = []
            for shablon_id, soni in kiritilganlar.items():
                sh = await conn.fetchrow(
                    "SELECT nomi FROM shablonlar WHERE id=$1 AND product_id=$2",
                    shablon_id, product_id)
                if not sh:
                    return False, {"shablon_yoq": True}
                chiqim = await _shablon_bloklari(conn, shablon_id, soni)
                for kod, n in chiqim.items():
                    blok_jami[kod] = blok_jami.get(kod, 0) + n
                shablon_satrlar.append({"nomi": sh["nomi"], "soni": soni})

            # Formula + materiallarni QULFLAB o'qiymiz
            formula = await conn.fetch("""
                SELECT m.id, m.nomi, m.qoldiq, m.asl_birlik, q.miqdor_asosiy
                FROM qolip_formula q
                JOIN materials m ON q.material_id = m.id
                WHERE q.product_id=$1
                FOR UPDATE OF m
            """, product_id)
            if not formula:
                return False, {"formula_yoq": True}

            # Yetarlilik tekshiruvi
            yetishmaydi = []
            for f in formula:
                kerak = f["miqdor_asosiy"] * jami_qolip
                if f["qoldiq"] < kerak:
                    asl = f["asl_birlik"]
                    yetishmaydi.append({
                        "nomi": f["nomi"],
                        "kerak_asl": asosiydan_birlikga(kerak, asl),
                        "bor_asl": asosiydan_birlikga(f["qoldiq"], asl),
                        "birlik": asl,
                    })
            if yetishmaydi:
                return False, {"yetishmaydi": yetishmaydi}

            # Ishlab chiqarish yozuvlari (har shablon uchun)
            prod_ids = []
            for shablon_id, soni in kiritilganlar.items():
                r = await conn.fetchrow("""
                    INSERT INTO production_log (sana, shablon_id, qolip_soni, user_id, product_id)
                    VALUES ($1, $2, $3, $4, $5) RETURNING id
                """, sana_str, shablon_id, soni, user_id, product_id)
                prod_ids.append((r["id"], soni))

            # Minimum chegaralar
            min_rows = await conn.fetch("SELECT material_id, min_chegara FROM settings")
            min_map = {r["material_id"]: r["min_chegara"] for r in min_rows}

            sarflar = []
            ogohlantirish = []
            for f in formula:
                material_id = f["id"]
                nomi = f["nomi"]
                asl = f["asl_birlik"]
                miqdor_asosiy = f["miqdor_asosiy"]
                ketgan_asosiy = miqdor_asosiy * jami_qolip

                new_row = await conn.fetchrow(
                    "UPDATE materials SET qoldiq = qoldiq - $1 WHERE id = $2 RETURNING qoldiq",
                    ketgan_asosiy, material_id
                )
                yangi_qoldiq = new_row["qoldiq"]

                for pid, soni in prod_ids:
                    ketgan_bu = miqdor_asosiy * soni
                    await conn.execute("""
                        INSERT INTO material_chiqim_log
                        (production_log_id, material_id, material_nomi, ketgan_miqdor,
                         birlik, sana, product_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, pid, material_id, nomi, ketgan_bu, asl, sana_str, product_id)

                sarflar.append({
                    "nomi": nomi,
                    "ketgan_asl": asosiydan_birlikga(ketgan_asosiy, asl),
                    "qoldiq_asl": asosiydan_birlikga(yangi_qoldiq, asl),
                    "birlik": asl,
                })

                min_ch = min_map.get(material_id)
                if min_ch and yangi_qoldiq <= min_ch:
                    ogohlantirish.append({
                        "nomi": nomi,
                        "qoldiq_asl": asosiydan_birlikga(yangi_qoldiq, asl),
                        "min_asl": asosiydan_birlikga(min_ch, asl),
                        "birlik": asl,
                    })

            # Tayyor mahsulotga qo'shish
            blok_nomlari = {}
            brows = await conn.fetch(
                "SELECT kod, nomi FROM mahsulot_bloklari WHERE product_id=$1", product_id)
            for b in brows:
                blok_nomlari[b["kod"]] = b["nomi"]

            for kod, n in blok_jami.items():
                if n > 0:
                    await conn.execute("""
                        INSERT INTO finished_goods (product_id, block_type, qoldiq)
                        VALUES ($1,$2,$3)
                        ON CONFLICT (product_id, block_type)
                        DO UPDATE SET qoldiq = finished_goods.qoldiq + $3
                    """, product_id, kod, n)

            mahsulot = await conn.fetchrow(
                "SELECT nomi FROM mahsulotlar WHERE id=$1", product_id)
            urow = await conn.fetchrow("SELECT ism, rol FROM users WHERE id=$1", user_id)
            blok_matn = ", ".join(f"{blok_nomlari.get(k, k)}: {v}" for k, v in blok_jami.items())
            await conn.execute("""
                INSERT INTO audit_log (user_id, ism, rol, amal, tafsilot)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id,
                urow["ism"] if urow else str(user_id),
                urow["rol"] if urow else "-",
                "Ishlab chiqarish kiritildi",
                f"{mahsulot['nomi'] if mahsulot else ''} | Qolip: {jami_qolip} | {blok_matn}")

    return True, {
        "mahsulot_nomi": mahsulot["nomi"] if mahsulot else "",
        "jami_qolip": jami_qolip,
        "bloklar": {blok_nomlari.get(k, k): v for k, v in blok_jami.items()},
        "shablonlar": shablon_satrlar,
        "sarflar": sarflar,
        "ogohlantirish": ogohlantirish,
    }


async def delete_last_production_with_restore(product_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, shablon_id, qolip_soni FROM production_log "
                "WHERE product_id=$1 ORDER BY id DESC LIMIT 1", product_id)
            if not row:
                return False, "❌ O'chiriladigan yozuv yo'q!"

            prod_id = row["id"]
            blok_jami = await _shablon_bloklari(conn, row["shablon_id"], row["qolip_soni"])

            for kod, n in blok_jami.items():
                if n > 0:
                    await conn.execute(
                        "UPDATE finished_goods SET qoldiq=GREATEST(0, qoldiq-$1) "
                        "WHERE product_id=$2 AND block_type=$3", n, product_id, kod)

            chiqim_logs = await conn.fetch(
                "SELECT material_id, material_nomi, ketgan_miqdor, birlik "
                "FROM material_chiqim_log WHERE production_log_id=$1", prod_id)

            qaytarilgan = []
            for ch in chiqim_logs:
                await conn.execute(
                    "UPDATE materials SET qoldiq = qoldiq + $1 WHERE id=$2",
                    ch["ketgan_miqdor"], ch["material_id"])
                asl = ch["birlik"] or "kg"
                asl_miqdor = asosiydan_birlikga(ch["ketgan_miqdor"], asl)
                qaytarilgan.append(f"   {ch['material_nomi']}: +{asl_miqdor:.2f} {asl}")

            await conn.execute(
                "DELETE FROM material_chiqim_log WHERE production_log_id=$1", prod_id)
            await conn.execute("DELETE FROM production_log WHERE id=$1", prod_id)

            blok_matn = ", ".join(f"{k}: {v}" for k, v in blok_jami.items())
            tafsilot = f"{row['qolip_soni']} qolip o'chirildi | Bloklar: {blok_matn}\n"
            if qaytarilgan:
                tafsilot += "Omborga qaytarildi:\n" + "\n".join(qaytarilgan)
            else:
                tafsilot += "(Chiqim tarixi topilmadi)"
            return True, tafsilot


async def get_production_today(product_id):
    """Bugungi ishlab chiqarish: {jami_qolip, shablonlar:[{nomi,soni}], bloklar:{nomi:soni}}."""
    bugun = bugungi_sana().isoformat()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.shablon_id, s.nomi AS shablon_nomi,
                   COALESCE(SUM(p.qolip_soni),0) AS qty
            FROM production_log p
            LEFT JOIN shablonlar s ON p.shablon_id=s.id
            WHERE p.product_id=$1 AND p.sana=$2
            GROUP BY p.shablon_id, s.nomi
        """, product_id, bugun)
        jami_qolip = 0
        shablonlar = []
        blok_jami = {}
        for r in rows:
            qty = int(r["qty"])
            jami_qolip += qty
            shablonlar.append({"nomi": r["shablon_nomi"] or "?", "soni": qty})
            chiqim = await _shablon_bloklari(conn, r["shablon_id"], qty)
            for kod, n in chiqim.items():
                blok_jami[kod] = blok_jami.get(kod, 0) + n
        # Blok nomlari
        blok_nomlari = {}
        for b in await conn.fetch(
                "SELECT kod, nomi FROM mahsulot_bloklari WHERE product_id=$1", product_id):
            blok_nomlari[b["kod"]] = b["nomi"]
        return {
            "jami_qolip": jami_qolip,
            "shablonlar": shablonlar,
            "bloklar": {blok_nomlari.get(k, k): v for k, v in blok_jami.items()},
        }



# ════════════════════════════════════════════════════════════════════
# SOTUV (product-aware, atomik)
# ════════════════════════════════════════════════════════════════════
async def add_sales_log(product_id, block_kod, miqdor, user_id=None):
    """Atomik: FOR UPDATE bilan oshirib sotishni oldini oladi. Narxni snapshot qiladi."""
    sana_str = bugungi_sana().isoformat()
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT qoldiq FROM finished_goods WHERE product_id=$1 AND block_type=$2 FOR UPDATE",
                product_id, block_kod
            )
            joriy_qoldiq = row["qoldiq"] if row else 0
            if joriy_qoldiq < miqdor:
                return False, (
                    f"❌ Tayyor mahsulot yetarli emas!\n"
                    f"   {block_kod}: bor {joriy_qoldiq} ta, kerak {miqdor} ta"
                )
            narx_row = await conn.fetchrow(
                "SELECT sotuv_narx FROM mahsulot_bloklari WHERE product_id=$1 AND kod=$2",
                product_id, block_kod)
            narx = float(narx_row["sotuv_narx"]) if narx_row and narx_row["sotuv_narx"] else 0.0
            await conn.execute(
                "INSERT INTO sales_log (sana, block_type, miqdor, user_id, narx, product_id) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                sana_str, block_kod, miqdor, user_id, narx, product_id
            )
            await conn.execute(
                "UPDATE finished_goods SET qoldiq=qoldiq-$1 WHERE product_id=$2 AND block_type=$3",
                miqdor, product_id, block_kod)
            return True, "✅ Sotuv kiritildi!"


async def delete_last_sale(product_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, block_type, miqdor FROM sales_log "
                "WHERE product_id=$1 ORDER BY id DESC LIMIT 1 FOR UPDATE", product_id)
            if row:
                await conn.execute("DELETE FROM sales_log WHERE id=$1", row["id"])
                await conn.execute(
                    "UPDATE finished_goods SET qoldiq=qoldiq+$1 "
                    "WHERE product_id=$2 AND block_type=$3",
                    row["miqdor"], product_id, row["block_type"])
                return True
            return False


async def get_sales_today(product_id):
    """{bloklar:[{kod,nomi,qty}], jami}."""
    bugun = bugungi_sana().isoformat()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT s.block_type AS kod, b.nomi AS nomi,
                   COALESCE(SUM(s.miqdor),0) AS qty
            FROM sales_log s
            LEFT JOIN mahsulot_bloklari b
                ON b.product_id=s.product_id AND b.kod=s.block_type
            WHERE s.product_id=$1 AND s.sana=$2
            GROUP BY s.block_type, b.nomi
        """, product_id, bugun)
        bloklar = [dict(r) for r in rows]
        jami = sum(int(r["qty"]) for r in bloklar)
        return {"bloklar": bloklar, "jami": jami}


# ════════════════════════════════════════════════════════════════════
# INVENTARIZATSIYA (product-aware)
# ════════════════════════════════════════════════════════════════════
async def add_inventarizatsiya(product_id, sana, block_kod, bot_hisob,
                               real_hisob, izoh, user_id):
    sana_str = sana.isoformat() if hasattr(sana, "isoformat") else str(sana)
    farq = real_hisob - bot_hisob
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO inventarizatsiya
            (sana, block_type, bot_hisob, real_hisob, farq, izoh, user_id, product_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """, sana_str, block_kod, bot_hisob, real_hisob, farq, izoh, user_id, product_id)
        await conn.execute(
            "INSERT INTO finished_goods (product_id, block_type, qoldiq) VALUES ($1,$2,$3) "
            "ON CONFLICT (product_id, block_type) DO UPDATE SET qoldiq=$3",
            product_id, block_kod, real_hisob)
    return farq

async def get_inventarizatsiya_tarixi(limit=20):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT i.*, u.ism AS user_ism, m.nomi AS product_nomi
            FROM inventarizatsiya i
            LEFT JOIN users u ON i.user_id = u.id
            LEFT JOIN mahsulotlar m ON i.product_id = m.id
            ORDER BY i.vaqt DESC LIMIT $1
        """, limit)
        return [dict(r) for r in rows]


# ── Bot sozlamalari ──
async def get_bot_setting(kalit):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT qiymat FROM bot_settings WHERE kalit=$1", kalit)
        return row["qiymat"] if row else None

async def set_bot_setting(kalit, qiymat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_settings (kalit, qiymat) VALUES ($1,$2)
            ON CONFLICT (kalit) DO UPDATE SET qiymat=$2
        """, kalit, qiymat)

# ── Minimum chegara sozlamalari ──
async def get_settings():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.nomi, s.min_chegara, m.birlik, m.id, m.asl_birlik
            FROM settings s
            JOIN materials m ON s.material_id = m.id
        """)
        return [tuple(r) for r in rows]

async def set_min_chegara(material_id, min_chegara):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (material_id, min_chegara) VALUES ($1,$2)
            ON CONFLICT (material_id) DO UPDATE SET min_chegara=$2
        """, material_id, min_chegara)

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

async def update_user_til(user_id: int, til: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET til=$1 WHERE id=$2", til, user_id)

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

# ── Material narxlari (UZS, baza birligi) ──
async def get_material_narxlar():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, narx FROM materials")
        return {r["id"]: (r["narx"] or 0.0) for r in rows}

async def set_material_narx(material_id, narx_asosiy):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE materials SET narx=$1 WHERE id=$2", float(narx_asosiy), material_id)


# ════════════════════════════════════════════════════════════════════
# TANNARX (product-aware, dinamik)
# ════════════════════════════════════════════════════════════════════
async def tannarx_hisobla(product_id):
    """
    Berilgan mahsulot uchun 1 qolip va har bir blok tannarxini hisoblaydi (UZS).
    1 blok = qolip_tannarxi / qolip_dona (yoki override).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        formula = await conn.fetch("""
            SELECT m.nomi, m.asl_birlik, q.miqdor_asosiy, COALESCE(m.narx, 0) AS narx
            FROM qolip_formula q
            JOIN materials m ON q.material_id = m.id
            WHERE q.product_id=$1
        """, product_id)
        mahsulot = await conn.fetchrow(
            "SELECT ishchi_haqi, qoshimcha_xarajat FROM mahsulotlar WHERE id=$1", product_id)
        bloklar = await conn.fetch(
            "SELECT id, kod, nomi, olcham, qolip_dona, tannarx_override "
            "FROM mahsulot_bloklari WHERE product_id=$1 ORDER BY tartib, id", product_id)

    material_cost = 0.0
    tafsil = []
    for f in formula:
        summa = f["miqdor_asosiy"] * (f["narx"] or 0.0)
        material_cost += summa
        tafsil.append({"nomi": f["nomi"], "summa": summa})

    ishchi = float(mahsulot["ishchi_haqi"]) if mahsulot else 0.0
    qoshimcha = float(mahsulot["qoshimcha_xarajat"]) if mahsulot else 0.0
    qolip = material_cost + ishchi + qoshimcha

    blok_natija = []
    for b in bloklar:
        dona = b["qolip_dona"] or 0
        auto = (qolip / dona) if dona else 0.0
        over = b["tannarx_override"]
        over = float(over) if over is not None else None
        blok_natija.append({
            "id": b["id"], "kod": b["kod"], "nomi": b["nomi"], "olcham": b["olcham"],
            "qolip_dona": dona, "auto": auto, "override": over,
            "final": over if over is not None else auto,
        })

    return {
        "material": material_cost, "ishchi": ishchi, "qoshimcha": qoshimcha,
        "qolip": qolip, "tafsil": tafsil, "bloklar": blok_natija,
    }


async def get_block_tannarx_map():
    """{(product_id, block_kod): tannarx_uzs} — barcha mahsulotlar bo'yicha (COGS uchun)."""
    natija = {}
    for m in await get_mahsulotlar(faqat_faol=False):
        ti = await tannarx_hisobla(m["id"])
        for b in ti["bloklar"]:
            natija[(m["id"], b["kod"])] = b["final"]
    return natija



# ════════════════════════════════════════════════════════════════════
# HISOBOT AGREGATLARI (product-aware)
# ════════════════════════════════════════════════════════════════════
def _d(x):
    return x.isoformat() if hasattr(x, "isoformat") else str(x)


async def ombor_xom_qiymati():
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(qoldiq * COALESCE(narx, 0)), 0) AS jami FROM materials")
        return float(row["jami"]) if row else 0.0


async def get_production_qolip_range(boshliq, oxiri, product_id=None):
    """{product_id: {'nomi':.., 'qolip':..}}."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if product_id:
            rows = await conn.fetch("""
                SELECT p.product_id, m.nomi, COALESCE(SUM(p.qolip_soni),0) AS qolip
                FROM production_log p LEFT JOIN mahsulotlar m ON m.id=p.product_id
                WHERE p.sana BETWEEN $1 AND $2 AND p.product_id=$3
                GROUP BY p.product_id, m.nomi
            """, _d(boshliq), _d(oxiri), product_id)
        else:
            rows = await conn.fetch("""
                SELECT p.product_id, m.nomi, COALESCE(SUM(p.qolip_soni),0) AS qolip
                FROM production_log p LEFT JOIN mahsulotlar m ON m.id=p.product_id
                WHERE p.sana BETWEEN $1 AND $2
                GROUP BY p.product_id, m.nomi
            """, _d(boshliq), _d(oxiri))
        return {r["product_id"]: {"nomi": r["nomi"] or "?", "qolip": int(r["qolip"])}
                for r in rows}


async def get_production_blocks_range(boshliq, oxiri, product_id=None):
    """[{product_id, product_nomi, kod, blok_nomi, soni}]."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        q = """
            SELECT p.product_id, m.nomi AS product_nomi, sc.block_kod AS kod,
                   b.nomi AS blok_nomi, COALESCE(SUM(sc.soni * p.qolip_soni),0) AS soni
            FROM production_log p
            JOIN shablon_chiqim sc ON sc.shablon_id = p.shablon_id
            LEFT JOIN mahsulotlar m ON m.id = p.product_id
            LEFT JOIN mahsulot_bloklari b ON b.product_id=p.product_id AND b.kod=sc.block_kod
            WHERE p.sana BETWEEN $1 AND $2
        """
        if product_id:
            q += " AND p.product_id=$3 GROUP BY p.product_id, m.nomi, sc.block_kod, b.nomi"
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri), product_id)
        else:
            q += " GROUP BY p.product_id, m.nomi, sc.block_kod, b.nomi"
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri))
        return [{"product_id": r["product_id"], "product_nomi": r["product_nomi"] or "?",
                 "kod": r["kod"], "blok_nomi": r["blok_nomi"] or r["kod"],
                 "soni": int(r["soni"])} for r in rows]


async def get_sales_blocks_range(boshliq, oxiri, product_id=None):
    """[{product_id, product_nomi, kod, blok_nomi, qty, rev}]."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        q = """
            SELECT s.product_id, m.nomi AS product_nomi, s.block_type AS kod,
                   b.nomi AS blok_nomi,
                   COALESCE(SUM(s.miqdor),0) AS qty,
                   COALESCE(SUM(s.miqdor * COALESCE(s.narx,0)),0) AS rev
            FROM sales_log s
            LEFT JOIN mahsulotlar m ON m.id = s.product_id
            LEFT JOIN mahsulot_bloklari b ON b.product_id=s.product_id AND b.kod=s.block_type
            WHERE s.sana BETWEEN $1 AND $2
        """
        if product_id:
            q += " AND s.product_id=$3 GROUP BY s.product_id, m.nomi, s.block_type, b.nomi"
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri), product_id)
        else:
            q += " GROUP BY s.product_id, m.nomi, s.block_type, b.nomi"
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri))
        return [{"product_id": r["product_id"], "product_nomi": r["product_nomi"] or "?",
                 "kod": r["kod"], "blok_nomi": r["blok_nomi"] or r["kod"],
                 "qty": int(r["qty"]), "rev": float(r["rev"])} for r in rows]


async def get_production_detail_range(boshliq, oxiri, product_id=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        q = """
            SELECT p.sana, p.qolip_soni, p.vaqt,
                   m.nomi AS product_nomi, s.nomi AS shablon_nomi,
                   u.ism AS user_ism, u.rol AS user_rol
            FROM production_log p
            LEFT JOIN mahsulotlar m ON m.id=p.product_id
            LEFT JOIN shablonlar s ON s.id=p.shablon_id
            LEFT JOIN users u ON u.id=p.user_id
            WHERE p.sana BETWEEN $1 AND $2
        """
        if product_id:
            q += " AND p.product_id=$3 ORDER BY p.vaqt DESC"
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri), product_id)
        else:
            q += " ORDER BY p.vaqt DESC"
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri))
        return [dict(r) for r in rows]


async def get_sales_detail_range(boshliq, oxiri, product_id=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        q = """
            SELECT s.sana, s.block_type, s.miqdor, s.vaqt,
                   m.nomi AS product_nomi, b.nomi AS blok_nomi,
                   u.ism AS user_ism, u.rol AS user_rol
            FROM sales_log s
            LEFT JOIN mahsulotlar m ON m.id=s.product_id
            LEFT JOIN mahsulot_bloklari b ON b.product_id=s.product_id AND b.kod=s.block_type
            LEFT JOIN users u ON u.id=s.user_id
            WHERE s.sana BETWEEN $1 AND $2
        """
        if product_id:
            q += " AND s.product_id=$3 ORDER BY s.vaqt DESC"
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri), product_id)
        else:
            q += " ORDER BY s.vaqt DESC"
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri))
        return [dict(r) for r in rows]


async def get_production_daily(boshliq, oxiri, product_id=None):
    """[{sana, qolip}]."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if product_id:
            rows = await conn.fetch("""
                SELECT sana, COALESCE(SUM(qolip_soni),0) AS qolip
                FROM production_log WHERE sana BETWEEN $1 AND $2 AND product_id=$3
                GROUP BY sana ORDER BY sana
            """, _d(boshliq), _d(oxiri), product_id)
        else:
            rows = await conn.fetch("""
                SELECT sana, COALESCE(SUM(qolip_soni),0) AS qolip
                FROM production_log WHERE sana BETWEEN $1 AND $2
                GROUP BY sana ORDER BY sana
            """, _d(boshliq), _d(oxiri))
        return [{"sana": r["sana"], "qolip": int(r["qolip"])} for r in rows]


async def get_sales_daily(boshliq, oxiri, product_id=None):
    """[{sana, qty, rev}]."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if product_id:
            rows = await conn.fetch("""
                SELECT sana, COALESCE(SUM(miqdor),0) AS qty,
                       COALESCE(SUM(miqdor*COALESCE(narx,0)),0) AS rev
                FROM sales_log WHERE sana BETWEEN $1 AND $2 AND product_id=$3
                GROUP BY sana ORDER BY sana
            """, _d(boshliq), _d(oxiri), product_id)
        else:
            rows = await conn.fetch("""
                SELECT sana, COALESCE(SUM(miqdor),0) AS qty,
                       COALESCE(SUM(miqdor*COALESCE(narx,0)),0) AS rev
                FROM sales_log WHERE sana BETWEEN $1 AND $2
                GROUP BY sana ORDER BY sana
            """, _d(boshliq), _d(oxiri))
        return [{"sana": r["sana"], "qty": int(r["qty"]), "rev": float(r["rev"])}
                for r in rows]


async def get_material_sarfi(boshliq, oxiri, product_id=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        q = """
            SELECT cl.material_id, cl.material_nomi, cl.birlik,
                   COALESCE(SUM(cl.ketgan_miqdor), 0) AS jami,
                   COALESCE(m.narx, 0) AS narx
            FROM material_chiqim_log cl
            LEFT JOIN materials m ON cl.material_id = m.id
            WHERE cl.sana BETWEEN $1 AND $2
        """
        if product_id:
            q += (" AND cl.product_id=$3 GROUP BY cl.material_id, cl.material_nomi, "
                  "cl.birlik, m.narx ORDER BY jami DESC")
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri), product_id)
        else:
            q += (" GROUP BY cl.material_id, cl.material_nomi, cl.birlik, m.narx "
                  "ORDER BY jami DESC")
            rows = await conn.fetch(q, _d(boshliq), _d(oxiri))
        return [{"material_id": r["material_id"], "nomi": r["material_nomi"],
                 "birlik": r["birlik"], "jami": float(r["jami"]),
                 "narx": float(r["narx"] or 0)} for r in rows]


async def get_production_by_user_range(boshliq, oxiri):
    """[{user_id, ism, rol, qolip, haq}] — ish haqi mahsulotga xos."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.user_id, u.ism AS ism, u.rol AS rol,
                   COALESCE(m.ishchi_haqi,0) AS ishchi_haqi,
                   COALESCE(SUM(p.qolip_soni),0) AS qty
            FROM production_log p
            LEFT JOIN users u ON u.id = p.user_id
            LEFT JOIN mahsulotlar m ON m.id = p.product_id
            WHERE p.sana BETWEEN $1 AND $2
            GROUP BY p.user_id, u.ism, u.rol, m.ishchi_haqi
        """, _d(boshliq), _d(oxiri))
    agg = {}
    for r in rows:
        uid = r["user_id"]
        d = agg.setdefault(uid, {
            "user_id": uid, "ism": r["ism"] or "Noma'lum",
            "rol": r["rol"] or "-", "qolip": 0, "haq": 0.0})
        qty = int(r["qty"])
        d["qolip"] += qty
        d["haq"] += qty * float(r["ishchi_haqi"] or 0)
    return sorted(agg.values(), key=lambda x: x["qolip"], reverse=True)


async def get_sales_by_user_range(boshliq, oxiri):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT s.user_id, u.ism AS ism, u.rol AS rol,
                   COALESCE(SUM(s.miqdor), 0) AS qty,
                   COALESCE(SUM(s.miqdor * COALESCE(s.narx, 0)), 0) AS rev
            FROM sales_log s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.sana BETWEEN $1 AND $2
            GROUP BY s.user_id, u.ism, u.rol
            ORDER BY qty DESC
        """, _d(boshliq), _d(oxiri))
        return [{"user_id": r["user_id"], "ism": r["ism"] or "Noma'lum",
                 "rol": r["rol"] or "-", "qty": int(r["qty"]),
                 "rev": float(r["rev"])} for r in rows]


# ── Hisobot obunachilari ──
async def add_hisobot_obunachi(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO hisobot_obunachilar (user_id) VALUES ($1) "
            "ON CONFLICT (user_id) DO NOTHING", user_id)

async def remove_hisobot_obunachi(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM hisobot_obunachilar WHERE user_id=$1", user_id)

async def get_hisobot_obunachilar():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM hisobot_obunachilar")
        return [r["user_id"] for r in rows]


# ── Foydalanuvchi lifecycle ──
async def add_pending(user_id, ism, username):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO pending_users (user_id, ism, username, vaqt)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (user_id) DO UPDATE SET ism=$2, username=$3, vaqt=NOW()
        """, user_id, ism, username)

async def get_pending():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, ism, username FROM pending_users ORDER BY vaqt DESC")
        return [dict(r) for r in rows]

async def get_pending_one(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id, ism, username FROM pending_users WHERE user_id=$1", user_id)
        return dict(row) if row else None

async def remove_pending(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pending_users WHERE user_id=$1", user_id)

async def unblock_user(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET faol=TRUE WHERE id=$1", user_id)

async def get_blocked_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM users WHERE faol=FALSE ORDER BY qoshilgan_vaqt DESC")
        return [dict(r) for r in rows]

async def update_user_ism(user_id, ism):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET ism=$1 WHERE id=$2", ism, user_id)

async def update_user_username(user_id, username):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET username=$1 WHERE id=$2", username, user_id)

async def touch_user(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET oxirgi_faollik=NOW() WHERE id=$1 AND faol=TRUE", user_id)

async def get_user_stats(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        qolip = await conn.fetchval(
            "SELECT COALESCE(SUM(qolip_soni),0) FROM production_log WHERE user_id=$1",
            user_id) or 0
        srow = await conn.fetchrow(
            "SELECT COALESCE(SUM(miqdor),0) AS qty, "
            "COALESCE(SUM(miqdor*COALESCE(narx,0)),0) AS rev "
            "FROM sales_log WHERE user_id=$1", user_id)
    return {
        "qolip": int(qolip),
        "sotuv_qty": int(srow["qty"]) if srow else 0,
        "sotuv_rev": float(srow["rev"]) if srow else 0.0,
    }
