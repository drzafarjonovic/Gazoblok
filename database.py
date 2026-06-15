import asyncpg
import asyncio
import os
import time
from datetime import datetime, date, timezone, timedelta

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

# ── Shablon → blok hisobi (markazlashtirilgan, DRY) ──
# Har bir shablon 1 qolipdan nechta A va B blok beradi
SHABLON_BLOK = {
    1: (12, 0),    # Shablon 1: 12 A
    2: (0, 24),    # Shablon 2: 24 B
    3: (11, 2),    # Shablon 3: 11 A + 2 B
}

def shablon_bloklari(shablon, qolip_soni):
    """Berilgan shablon va qolip soni uchun (A_blok, B_blok) qaytaradi."""
    a, b = SHABLON_BLOK.get(shablon, (0, 0))
    return a * qolip_soni, b * qolip_soni


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

# 10 ta permission
BARCHA_PERMISSIONLAR = [
    "ishlab_chiqarish_kiritish",
    "ishlab_chiqarish_korish",
    "sotuv_kiritish",
    "sotuv_korish",
    "ombor_kiritish",
    "ombor_korish",
    "tayyor_mahsulot_korish",
    "tayyor_mahsulot_tahrirlash",
    "hisobot_korish",
    "excel_hisobot",
]

# Standart rol huquqlari
STANDART_ROL_PERMISSIONLAR = {
    "superadmin": {p: True for p in BARCHA_PERMISSIONLAR},
    "direktor": {
        "ishlab_chiqarish_kiritish": False,
        "ishlab_chiqarish_korish": True,
        "sotuv_kiritish": False,
        "sotuv_korish": True,
        "ombor_kiritish": False,
        "ombor_korish": True,
        "tayyor_mahsulot_korish": True,
        "tayyor_mahsulot_tahrirlash": False,
        "hisobot_korish": True,
        "excel_hisobot": True,
    },
    "omborchi": {
        "ishlab_chiqarish_kiritish": False,
        "ishlab_chiqarish_korish": True,
        "sotuv_kiritish": False,
        "sotuv_korish": False,
        "ombor_kiritish": True,
        "ombor_korish": True,
        "tayyor_mahsulot_korish": True,
        "tayyor_mahsulot_tahrirlash": True,
        "hisobot_korish": True,
        "excel_hisobot": False,
    },
    "ishchi": {
        "ishlab_chiqarish_kiritish": True,
        "ishlab_chiqarish_korish": True,
        "sotuv_kiritish": False,
        "sotuv_korish": False,
        "ombor_kiritish": False,
        "ombor_korish": True,
        "tayyor_mahsulot_korish": False,
        "tayyor_mahsulot_tahrirlash": False,
        "hisobot_korish": False,
        "excel_hisobot": False,
    },
    "sotuvchi": {
        "ishlab_chiqarish_kiritish": False,
        "ishlab_chiqarish_korish": False,
        "sotuv_kiritish": True,
        "sotuv_korish": True,
        "ombor_kiritish": False,
        "ombor_korish": False,
        "tayyor_mahsulot_korish": True,
        "tayyor_mahsulot_tahrirlash": False,
        "hisobot_korish": False,
        "excel_hisobot": False,
    },
    "hisobchi": {
        "ishlab_chiqarish_kiritish": False,
        "ishlab_chiqarish_korish": True,
        "sotuv_kiritish": False,
        "sotuv_korish": True,
        "ombor_kiritish": False,
        "ombor_korish": True,
        "tayyor_mahsulot_korish": True,
        "tayyor_mahsulot_tahrirlash": False,
        "hisobot_korish": True,
        "excel_hisobot": True,
    },
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
                shablon INTEGER NOT NULL,
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
                block_type TEXT NOT NULL UNIQUE,
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
        # Rol permissions jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rol_permissions (
                id SERIAL PRIMARY KEY,
                rol TEXT NOT NULL,
                permission TEXT NOT NULL,
                ruxsat BOOLEAN DEFAULT FALSE,
                UNIQUE(rol, permission)
            )
        """)
        # Foydalanuvchi individual permissions
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                permission TEXT NOT NULL,
                ruxsat BOOLEAN DEFAULT FALSE,
                UNIQUE(user_id, permission)
            )
        """)
        # Xom ashyo chiqim tarixi
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
        # Inventarizatsiya
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
        # Translations jadvali (multilingual)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                id SERIAL PRIMARY KEY,
                original TEXT NOT NULL,
                til TEXT NOT NULL,
                tarjima TEXT NOT NULL,
                UNIQUE(original, til)
            )
        """)
        await conn.execute("""
            INSERT INTO finished_goods (block_type, qoldiq)
            VALUES ('A', 0), ('B', 0)
            ON CONFLICT (block_type) DO NOTHING
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
        # `til` ustuni keyinroq qo'shilgan; eski bazalarda bo'lmasligi mumkin
        await conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS til TEXT DEFAULT 'uz'"
        )
        # Narx/moliya moduli ustunlari
        await conn.execute(
            "ALTER TABLE materials ADD COLUMN IF NOT EXISTS narx DOUBLE PRECISION DEFAULT 0"
        )
        await conn.execute(
            "ALTER TABLE sales_log ADD COLUMN IF NOT EXISTS narx DOUBLE PRECISION DEFAULT 0"
        )
        # Valyuta kurslari cache jadvali (1 kod = kurs UZS)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS valyuta_kurslari (
                kod TEXT PRIMARY KEY,
                kurs DOUBLE PRECISION NOT NULL,
                vaqt_epoch DOUBLE PRECISION NOT NULL
            )
        """)
        # Avtomatik hisobot obunachilari
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS hisobot_obunachilar (
                user_id BIGINT PRIMARY KEY,
                vaqt TIMESTAMP DEFAULT NOW()
            )
        """)

# ── Permissions ──
async def get_user_permissions(user_id, rol):
    """Foydalanuvchining barcha permissionlarini qaytaradi"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Rol permissionlari
        rol_rows = await conn.fetch(
            "SELECT permission, ruxsat FROM rol_permissions WHERE rol=$1", rol
        )
        perms = {r["permission"]: r["ruxsat"] for r in rol_rows}

        # Individual permissionlar (ustunlik qiladi)
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

# ── Materiallar ──
async def get_materials():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, nomi, qoldiq, birlik, asl_birlik FROM materials"
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
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Tartib muhim! Avval bog'liq jadvallar
        await conn.execute("DELETE FROM material_chiqim_log")
        await conn.execute("DELETE FROM audit_log")
        await conn.execute("DELETE FROM sales_log")
        await conn.execute("DELETE FROM production_log")
        await conn.execute("DELETE FROM inventarizatsiya")
        await conn.execute("DELETE FROM settings")
        await conn.execute("DELETE FROM qolip_formula")
        await conn.execute("DELETE FROM materials")
        await conn.execute("UPDATE finished_goods SET qoldiq=0")

# ── Qolip formulasi ──
async def get_qolip_formula():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.nomi, q.miqdor, q.birlik, m.qoldiq, m.birlik,
                   m.id, q.miqdor_asosiy, m.asl_birlik
            FROM qolip_formula q
            JOIN materials m ON q.material_id = m.id
        """)
        return [tuple(r) for r in rows]

async def add_qolip_formula(material_id, miqdor, birlik):
    miqdor_asosiy, _ = birlikni_asosiyga(miqdor, birlik)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO qolip_formula (material_id,miqdor,birlik,miqdor_asosiy) VALUES ($1,$2,$3,$4)",
            material_id, miqdor, birlik, miqdor_asosiy
        )

async def clear_qolip_formula():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM qolip_formula")

# ── Material tekshiruvi ──
async def check_material_yetarli(jami_qolip):
    formula = await get_qolip_formula()
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

# ── Xom ashyo chiqim log ──
async def add_material_chiqim_log(production_log_id, material_id, material_nomi,
                                   ketgan_miqdor, birlik, sana):
    """sana: date object yoki str"""
    sana_str = sana.isoformat() if hasattr(sana, 'isoformat') else str(sana)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO material_chiqim_log
            (production_log_id, material_id, material_nomi, ketgan_miqdor, birlik, sana)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, production_log_id, material_id, material_nomi, ketgan_miqdor, birlik, sana_str)

async def get_material_chiqim_range(boshliq, oxiri):
    """boshliq, oxiri: date object yoki str"""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT material_nomi, SUM(ketgan_miqdor) as jami, birlik, sana
            FROM material_chiqim_log
            WHERE sana BETWEEN $1 AND $2
            GROUP BY material_nomi, birlik, sana
            ORDER BY sana
        """, boshliq_str, oxiri_str)
        return [dict(r) for r in rows]

async def get_material_chiqim_by_material(material_nomi, boshliq, oxiri):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sana, SUM(ketgan_miqdor) as jami, birlik
            FROM material_chiqim_log
            WHERE material_nomi=$1 AND sana BETWEEN $2 AND $3
            GROUP BY sana, birlik
            ORDER BY sana
        """, material_nomi, boshliq, oxiri)
        return [dict(r) for r in rows]

# ── Ishlab chiqarish ──
async def add_production_log(sana, shablon, qolip_soni, user_id=None):
    """sana: date object yoki str"""
    # Date object bo'lsa, str ga o'zgartirish
    sana_str = sana.isoformat() if hasattr(sana, 'isoformat') else str(sana)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO production_log (sana, shablon, qolip_soni, user_id)
            VALUES ($1, $2, $3, $4) RETURNING id
        """, sana_str, shablon, qolip_soni, user_id)
        return row["id"]


async def add_production(kiritilganlar: dict, user_id):
    """
    Ishlab chiqarishni TO'LIQ atomik tranzaksiyada kiritadi:
    materiallarni qulflab (FOR UPDATE) tekshiradi, kamaytiradi,
    tayyor mahsulotga qo'shadi, chiqim log va audit yozadi.

    Args:
        kiritilganlar: {shablon: qolip_soni}
        user_id: kim kiritmoqda

    Returns:
        (True, payload_dict) muvaffaqiyatda,
        (False, {"yetishmaydi": [...]}) material yetishmasa.
    """
    s1 = int(kiritilganlar.get(1, 0))
    s2 = int(kiritilganlar.get(2, 0))
    s3 = int(kiritilganlar.get(3, 0))
    jami_qolip = s1 + s2 + s3
    if jami_qolip <= 0:
        return False, {"yetishmaydi": [], "bosh": True}

    a1, b1 = shablon_bloklari(1, s1)
    a3, b3 = shablon_bloklari(3, s3)
    a2, b2 = shablon_bloklari(2, s2)
    A_blok = a1 + a3 + a2
    B_blok = b1 + b3 + b2

    bugun = bugungi_sana()
    sana_str = bugun.isoformat()

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Formula + materiallarni QULFLAB o'qiymiz (race-condition oldini olish)
            formula = await conn.fetch("""
                SELECT m.id, m.nomi, m.qoldiq, m.asl_birlik, q.miqdor_asosiy
                FROM qolip_formula q
                JOIN materials m ON q.material_id = m.id
                FOR UPDATE OF m
            """)
            if not formula:
                return False, {"yetishmaydi": [], "formula_yoq": True}

            # Yetarlilikni tranzaksiya ichida qayta tekshiramiz
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

            # Ishlab chiqarish yozuvlari
            prod_ids = []
            for shablon, soni in ((1, s1), (2, s2), (3, s3)):
                if soni > 0:
                    r = await conn.fetchrow("""
                        INSERT INTO production_log (sana, shablon, qolip_soni, user_id)
                        VALUES ($1, $2, $3, $4) RETURNING id
                    """, sana_str, shablon, soni, user_id)
                    prod_ids.append((r["id"], shablon, soni))

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

                # ATOMIK kamaytirish (qulflangan, shuning uchun manfiy bo'lmaydi)
                new_row = await conn.fetchrow(
                    "UPDATE materials SET qoldiq = qoldiq - $1 WHERE id = $2 RETURNING qoldiq",
                    ketgan_asosiy, material_id
                )
                yangi_qoldiq = new_row["qoldiq"]

                # Chiqim log (har bir shablon uchun, to'g'ri birlikda)
                for pid, shablon, soni in prod_ids:
                    ketgan_bu = miqdor_asosiy * soni
                    await conn.execute("""
                        INSERT INTO material_chiqim_log
                        (production_log_id, material_id, material_nomi, ketgan_miqdor, birlik, sana)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """, pid, material_id, nomi, ketgan_bu, asl, sana_str)

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

            # Tayyor mahsulotga qo'shish (atomik)
            if A_blok > 0:
                await conn.execute(
                    "UPDATE finished_goods SET qoldiq = qoldiq + $1 WHERE block_type='A'", A_blok
                )
            if B_blok > 0:
                await conn.execute(
                    "UPDATE finished_goods SET qoldiq = qoldiq + $1 WHERE block_type='B'", B_blok
                )

            # Audit log (xuddi shu tranzaksiyada)
            urow = await conn.fetchrow("SELECT ism, rol FROM users WHERE id=$1", user_id)
            await conn.execute("""
                INSERT INTO audit_log (user_id, ism, rol, amal, tafsilot)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id,
                urow["ism"] if urow else str(user_id),
                urow["rol"] if urow else "-",
                "Ishlab chiqarish kiritildi",
                f"Qolip: {jami_qolip} ta | A: {A_blok} ta | B: {B_blok} ta")

    return True, {
        "jami_qolip": jami_qolip,
        "A_blok": A_blok, "B_blok": B_blok,
        "s1": s1, "s2": s2, "s3": s3,
        "sarflar": sarflar,
        "ogohlantirish": ogohlantirish,
    }

async def delete_last_production_with_restore():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, shablon, qolip_soni FROM production_log ORDER BY id DESC LIMIT 1"
            )
            if not row:
                return False, "❌ O'chiriladigan yozuv yo'q!"

            prod_id = row["id"]
            shablon = row["shablon"]
            qolip_soni = row["qolip_soni"]

            # Bloklar hisobi (markazlashtirilgan)
            A_blok, B_blok = shablon_bloklari(shablon, qolip_soni)

            # Tayyor mahsulot omboridan AYIRISH
            if A_blok > 0:
                await conn.execute(
                    "UPDATE finished_goods SET qoldiq=GREATEST(0, qoldiq-$1) WHERE block_type='A'",
                    A_blok
                )
            if B_blok > 0:
                await conn.execute(
                    "UPDATE finished_goods SET qoldiq=GREATEST(0, qoldiq-$1) WHERE block_type='B'",
                    B_blok
                )

            # Chiqim logdan materiallarni topib omborga qaytarish
            chiqim_logs = await conn.fetch(
                "SELECT material_id, material_nomi, ketgan_miqdor, birlik "
                "FROM material_chiqim_log WHERE production_log_id=$1",
                prod_id
            )

            qaytarilgan = []
            for ch in chiqim_logs:
                await conn.execute(
                    "UPDATE materials SET qoldiq=qoldiq+$1 WHERE id=$2",
                    ch["ketgan_miqdor"], ch["material_id"]
                )
                # Chiqim logdagi birlik (asl_birlik) bilan ko'rsatamiz
                asl = ch["birlik"] or "kg"
                asl_miqdor = asosiydan_birlikga(ch["ketgan_miqdor"], asl)
                qaytarilgan.append(
                    f"   {ch['material_nomi']}: +{asl_miqdor:.2f} {asl}"
                )

            # Loglarni o'chirish
            await conn.execute(
                "DELETE FROM material_chiqim_log WHERE production_log_id=$1", prod_id
            )
            await conn.execute(
                "DELETE FROM production_log WHERE id=$1", prod_id
            )

            tafsilot = f"Shablon {shablon}, {qolip_soni} qolip o'chirildi\n"
            tafsilot += f"Tayyor ombordan ayirildi: A={A_blok}, B={B_blok}\n"
            if qaytarilgan:
                tafsilot += "Omborga qaytarildi:\n" + "\n".join(qaytarilgan)
            else:
                tafsilot += "(Chiqim tarixi topilmadi)"

            return True, tafsilot

async def get_production_by_date(sana):
    """sana: date object yoki str"""
    sana_str = sana.isoformat() if hasattr(sana, 'isoformat') else str(sana)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT shablon, qolip_soni FROM production_log WHERE sana=$1", sana_str
        )
        return [tuple(r) for r in rows]

async def get_production_range(boshliq, oxiri):
    """boshliq, oxiri: date object yoki str"""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sana, shablon, qolip_soni
            FROM production_log
            WHERE sana BETWEEN $1 AND $2
            ORDER BY sana
        """, boshliq_str, oxiri_str)
        return [tuple(r) for r in rows]

async def get_production_detail_range(boshliq, oxiri):
    """Foydalanuvchi bilan to'liq ishlab chiqarish tarixi"""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.sana, p.shablon, p.qolip_soni,
                   u.ism as user_ism, u.rol as user_rol,
                   p.vaqt
            FROM production_log p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.sana BETWEEN $1 AND $2
            ORDER BY p.vaqt DESC
        """, boshliq_str, oxiri_str)
        return [dict(r) for r in rows]

# ── Sotuv ──
async def add_sales_log(sana, block_type, miqdor, user_id=None):
    """sana: date object yoki str. Atomik: FOR UPDATE bilan oshirib sotishni oldini oladi."""
    sana_str = sana.isoformat() if hasattr(sana, 'isoformat') else str(sana)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT qoldiq FROM finished_goods WHERE block_type=$1 FOR UPDATE",
                block_type
            )
            if not row:
                return False, "❌ Blok turi topilmadi!"
            joriy_qoldiq = row["qoldiq"]
            if joriy_qoldiq < miqdor:
                return False, (
                    f"❌ Tayyor mahsulot yetarli emas!\n"
                    f"   {block_type} blok: bor {joriy_qoldiq} ta, "
                    f"kerak {miqdor} ta"
                )
            # Sotuv narxini (UZS) snapshot qilamiz — tarixiy aniqlik uchun
            narx_kalit = "sotuv_narx_A" if block_type == "A" else "sotuv_narx_B"
            narx_row = await conn.fetchrow(
                "SELECT qiymat FROM bot_settings WHERE kalit=$1", narx_kalit
            )
            narx = (float(narx_row["qiymat"])
                    if narx_row and narx_row["qiymat"] not in (None, "") else 0.0)
            await conn.execute(
                "INSERT INTO sales_log (sana,block_type,miqdor,user_id,narx) "
                "VALUES ($1,$2,$3,$4,$5)",
                sana_str, block_type, miqdor, user_id, narx
            )
            await conn.execute(
                "UPDATE finished_goods SET qoldiq=qoldiq-$1 WHERE block_type=$2",
                miqdor, block_type
            )
            return True, "✅ Sotuv kiritildi!"

async def delete_last_sale():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, block_type, miqdor FROM sales_log ORDER BY id DESC LIMIT 1 FOR UPDATE"
            )
            if row:
                await conn.execute("DELETE FROM sales_log WHERE id=$1", row["id"])
                await conn.execute(
                    "UPDATE finished_goods SET qoldiq=qoldiq+$1 WHERE block_type=$2",
                    row["miqdor"], row["block_type"]
                )
                return True
            return False

async def get_sales_by_date(sana):
    """sana: date object yoki str"""
    sana_str = sana.isoformat() if hasattr(sana, 'isoformat') else str(sana)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT block_type, miqdor FROM sales_log WHERE sana=$1", sana_str
        )
        return [tuple(r) for r in rows]

async def get_sales_range(boshliq, oxiri):
    """boshliq, oxiri: date object yoki str"""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sana, block_type, miqdor
            FROM sales_log
            WHERE sana BETWEEN $1 AND $2
            ORDER BY sana
        """, boshliq_str, oxiri_str)
        return [tuple(r) for r in rows]

async def get_sales_detail_range(boshliq, oxiri):
    """Foydalanuvchi bilan to'liq sotuv tarixi"""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT s.sana, s.block_type, s.miqdor,
                   u.ism as user_ism, u.rol as user_rol,
                   s.vaqt
            FROM sales_log s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.sana BETWEEN $1 AND $2
            ORDER BY s.vaqt DESC
        """, boshliq_str, oxiri_str)
        return [dict(r) for r in rows]

# ── Tayyor mahsulot ──
async def get_finished_goods():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT block_type, qoldiq FROM finished_goods ORDER BY block_type"
        )
        return [tuple(r) for r in rows]

async def set_finished_goods(block_type, qoldiq):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE finished_goods SET qoldiq=$1 WHERE block_type=$2",
            qoldiq, block_type
        )

async def update_finished_goods(block_type, delta):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE finished_goods SET qoldiq=GREATEST(0,qoldiq+$1) WHERE block_type=$2",
            delta, block_type
        )

# ── Inventarizatsiya ──
async def add_inventarizatsiya(sana, block_type, bot_hisob, real_hisob, izoh, user_id):
    """sana: date object yoki str"""
    sana_str = sana.isoformat() if hasattr(sana, 'isoformat') else str(sana)
    farq = real_hisob - bot_hisob
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO inventarizatsiya
            (sana, block_type, bot_hisob, real_hisob, farq, izoh, user_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, sana_str, block_type, bot_hisob, real_hisob, farq, izoh, user_id)
        # Real hisobni bot ga ham kiritish
        await conn.execute(
            "UPDATE finished_goods SET qoldiq=$1 WHERE block_type=$2",
            real_hisob, block_type
        )
    return farq

async def get_inventarizatsiya_tarixi(limit=20):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT i.*, u.ism as user_ism
            FROM inventarizatsiya i
            LEFT JOIN users u ON i.user_id = u.id
            ORDER BY i.vaqt DESC LIMIT $1
        """, limit)
        return [dict(r) for r in rows]

# ── Bot sozlamalari ──
async def get_bot_setting(kalit):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT qiymat FROM bot_settings WHERE kalit=$1", kalit
        )
        return row["qiymat"] if row else None

async def set_bot_setting(kalit, qiymat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_settings (kalit, qiymat) VALUES ($1,$2)
            ON CONFLICT (kalit) DO UPDATE SET qiymat=$2
        """, kalit, qiymat)

# ── Sozlamalar ──
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
    """Tarjimani Supabase dan olish (cache)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tarjima FROM translations WHERE original=$1 AND til=$2",
            original, til
        )
        return row["tarjima"] if row else None

async def save_translation(original: str, til: str, tarjima: str):
    """Tarjimani Supabase ga saqlash"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO translations (original, til, tarjima)
            VALUES ($1, $2, $3)
            ON CONFLICT (original, til) DO NOTHING
        """, original, til, tarjima)

async def update_user_til(user_id: int, til: str):
    """Foydalanuvchi tilini yangilash"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET til=$1 WHERE id=$2", til, user_id
        )



# ── Valyuta kurslari (cache) ──
async def get_kurs(kod):
    """{'kurs':..., 'vaqt_epoch':...} yoki None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT kurs, vaqt_epoch FROM valyuta_kurslari WHERE kod=$1", kod
        )
        return dict(row) if row else None


async def set_kurs(kod, kurs):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO valyuta_kurslari (kod, kurs, vaqt_epoch)
            VALUES ($1, $2, $3)
            ON CONFLICT (kod) DO UPDATE SET kurs=$2, vaqt_epoch=$3
        """, kod, float(kurs), time.time())


# ── Material narxlari (UZS, baza birligi uchun) ──
async def get_material_narxlar():
    """{material_id: narx_asosiy_uzs}."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, narx FROM materials")
        return {r["id"]: (r["narx"] or 0.0) for r in rows}


async def set_material_narx(material_id, narx_asosiy):
    """narx_asosiy: 1 baza birlik (kg yoki litr) uchun narx, UZS da."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE materials SET narx=$1 WHERE id=$2", float(narx_asosiy), material_id
        )


# ── Tannarx hisobi (hammasi UZS da) ──
async def tannarx_hisobla():
    """
    1 qolip va 1 blok (A/B) tannarxini hisoblaydi (UZS).
    A = qolip/12, B = qolip/24 (hajm bo'yicha). Override bo'lsa o'sha ishlatiladi.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        formula = await conn.fetch("""
            SELECT m.nomi, m.asl_birlik, q.miqdor_asosiy, COALESCE(m.narx, 0) AS narx
            FROM qolip_formula q
            JOIN materials m ON q.material_id = m.id
        """)

    material_cost = 0.0
    tafsil = []
    for f in formula:
        ketgan = f["miqdor_asosiy"]
        narx = f["narx"] or 0.0
        summa = ketgan * narx
        material_cost += summa
        tafsil.append({
            "nomi": f["nomi"],
            "miqdor_asosiy": ketgan,
            "narx": narx,
            "summa": summa,
        })

    ishchi = float(await get_bot_setting("ishchi_haqi_qolip") or 0)
    qoshimcha = float(await get_bot_setting("qoshimcha_xarajat_qolip") or 0)
    qolip = material_cost + ishchi + qoshimcha

    A_auto = qolip / 12.0
    B_auto = qolip / 24.0

    A_over = await get_bot_setting("tannarx_override_A")
    B_over = await get_bot_setting("tannarx_override_B")
    A_over = float(A_over) if A_over not in (None, "") else None
    B_over = float(B_over) if B_over not in (None, "") else None

    return {
        "material": material_cost,
        "ishchi": ishchi,
        "qoshimcha": qoshimcha,
        "qolip": qolip,
        "A_auto": A_auto,
        "B_auto": B_auto,
        "A": A_over if A_over is not None else A_auto,
        "B": B_over if B_over is not None else B_auto,
        "A_override": A_over,
        "B_override": B_over,
        "tafsil": tafsil,
    }


# ── Daromad / ombor qiymati ──
async def get_sales_revenue_range(boshliq, oxiri):
    """Davr bo'yicha sotuv: {'A': (qty, revenue_uzs), 'B': (qty, revenue_uzs)}."""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT block_type,
                   COALESCE(SUM(miqdor), 0) AS qty,
                   COALESCE(SUM(miqdor * COALESCE(narx, 0)), 0) AS rev
            FROM sales_log
            WHERE sana BETWEEN $1 AND $2
            GROUP BY block_type
        """, boshliq_str, oxiri_str)
    natija = {"A": (0, 0.0), "B": (0, 0.0)}
    for r in rows:
        natija[r["block_type"]] = (int(r["qty"]), float(r["rev"]))
    return natija


async def ombor_xom_qiymati():
    """Ombordagi xom ashyo qiymati (UZS): Σ(qoldiq_asosiy × narx)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(qoldiq * COALESCE(narx, 0)), 0) AS jami FROM materials"
        )
        return float(row["jami"]) if row else 0.0



# ── Foydalanuvchi (ishchi) kesimida hisobot ──
async def get_production_by_user_range(boshliq, oxiri):
    """Davr bo'yicha har bir foydalanuvchining ishlab chiqarishi.
    [{user_id, ism, rol, qolip, A, B}] (qolip soni bo'yicha kamayuvchi)."""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.user_id, u.ism AS ism, u.rol AS rol,
                   p.shablon, COALESCE(SUM(p.qolip_soni), 0) AS qty
            FROM production_log p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.sana BETWEEN $1 AND $2
            GROUP BY p.user_id, u.ism, u.rol, p.shablon
        """, boshliq_str, oxiri_str)

    agg = {}
    for r in rows:
        uid = r["user_id"]
        d = agg.setdefault(uid, {
            "user_id": uid,
            "ism": r["ism"] or "Noma'lum",
            "rol": r["rol"] or "-",
            "qolip": 0, "A": 0, "B": 0,
        })
        a, b = shablon_bloklari(r["shablon"], r["qty"])
        d["qolip"] += r["qty"]
        d["A"] += a
        d["B"] += b
    return sorted(agg.values(), key=lambda x: x["qolip"], reverse=True)


async def get_sales_by_user_range(boshliq, oxiri):
    """Davr bo'yicha har bir foydalanuvchining sotuvi.
    [{user_id, ism, rol, qty, rev}] (miqdor bo'yicha kamayuvchi). rev — UZS."""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
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
        """, boshliq_str, oxiri_str)
        return [{
            "user_id": r["user_id"],
            "ism": r["ism"] or "Noma'lum",
            "rol": r["rol"] or "-",
            "qty": int(r["qty"]),
            "rev": float(r["rev"]),
        } for r in rows]



# ── Kunlik agregatlar (grafiklar uchun) ──
async def get_production_daily(boshliq, oxiri):
    """Kunlik ishlab chiqarish: [{sana, qolip, A, B}] (sana bo'yicha)."""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sana, shablon, COALESCE(SUM(qolip_soni), 0) AS qty
            FROM production_log
            WHERE sana BETWEEN $1 AND $2
            GROUP BY sana, shablon
        """, boshliq_str, oxiri_str)
    agg = {}
    for r in rows:
        d = agg.setdefault(r["sana"], {"sana": r["sana"], "qolip": 0, "A": 0, "B": 0})
        a, b = shablon_bloklari(r["shablon"], r["qty"])
        d["qolip"] += r["qty"]
        d["A"] += a
        d["B"] += b
    return [agg[k] for k in sorted(agg.keys())]


async def get_sales_daily(boshliq, oxiri):
    """Kunlik sotuv: [{sana, A, B, qty, rev}] (sana bo'yicha). rev — UZS."""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sana, block_type,
                   COALESCE(SUM(miqdor), 0) AS qty,
                   COALESCE(SUM(miqdor * COALESCE(narx, 0)), 0) AS rev
            FROM sales_log
            WHERE sana BETWEEN $1 AND $2
            GROUP BY sana, block_type
        """, boshliq_str, oxiri_str)
    agg = {}
    for r in rows:
        d = agg.setdefault(r["sana"], {"sana": r["sana"], "A": 0, "B": 0, "qty": 0, "rev": 0.0})
        if r["block_type"] == "A":
            d["A"] += int(r["qty"])
        elif r["block_type"] == "B":
            d["B"] += int(r["qty"])
        d["qty"] += int(r["qty"])
        d["rev"] += float(r["rev"])
    return [agg[k] for k in sorted(agg.keys())]



# ── Hisobot obunachilari (avtomatik hisobot qabul qiluvchilar) ──
async def add_hisobot_obunachi(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO hisobot_obunachilar (user_id) VALUES ($1) "
            "ON CONFLICT (user_id) DO NOTHING", user_id
        )


async def remove_hisobot_obunachi(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM hisobot_obunachilar WHERE user_id=$1", user_id
        )


async def get_hisobot_obunachilar():
    """Obunachilar user_id ro'yxati."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM hisobot_obunachilar")
        return [r["user_id"] for r in rows]



# ── Material sarfi (davr bo'yicha, narx bilan) ──
async def get_material_sarfi(boshliq, oxiri):
    """Davr bo'yicha har bir material sarfi:
    [{material_id, nomi, birlik, jami(asosiy), narx(asosiy_uzs)}] (jami bo'yicha)."""
    boshliq_str = boshliq.isoformat() if hasattr(boshliq, 'isoformat') else str(boshliq)
    oxiri_str = oxiri.isoformat() if hasattr(oxiri, 'isoformat') else str(oxiri)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT cl.material_id, cl.material_nomi, cl.birlik,
                   COALESCE(SUM(cl.ketgan_miqdor), 0) AS jami,
                   COALESCE(m.narx, 0) AS narx
            FROM material_chiqim_log cl
            LEFT JOIN materials m ON cl.material_id = m.id
            WHERE cl.sana BETWEEN $1 AND $2
            GROUP BY cl.material_id, cl.material_nomi, cl.birlik, m.narx
            ORDER BY jami DESC
        """, boshliq_str, oxiri_str)
        return [{
            "material_id": r["material_id"],
            "nomi": r["material_nomi"],
            "birlik": r["birlik"],
            "jami": float(r["jami"]),
            "narx": float(r["narx"] or 0),
        } for r in rows]
