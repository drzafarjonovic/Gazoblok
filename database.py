import asyncpg
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

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
    birlik = birlik.lower().strip()
    if birlik in BIRLIK_KG:
        return miqdor * BIRLIK_KG[birlik], "kg"
    elif birlik in BIRLIK_LITR:
        return miqdor * BIRLIK_LITR[birlik], "litr"
    return miqdor, birlik

def asosiydan_birlikga(miqdor_asosiy, birlik):
    birlik = birlik.lower().strip()
    if birlik in BIRLIK_KG:
        return miqdor_asosiy / BIRLIK_KG[birlik]
    elif birlik in BIRLIK_LITR:
        return miqdor_asosiy / BIRLIK_LITR[birlik]
    return miqdor_asosiy

# ── Rollar ──
ROLLAR = {
    "superadmin": "Super Admin",
    "direktor": "Direktor",
    "omborchi": "Omborchi",
    "ishchi": "Ishchi",
    "sotuvchi": "Sotuvchi",
    "hisobchi": "Hisobchi",
}

# ── Ulanish ──
async def get_conn():
    return await asyncpg.connect(DATABASE_URL)

# ── Database init ──
async def init_db():
    conn = await get_conn()
    try:
        # Foydalanuvchilar
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                ism TEXT NOT NULL,
                username TEXT,
                rol TEXT NOT NULL DEFAULT 'ishchi',
                qoshilgan_vaqt TIMESTAMP DEFAULT NOW(),
                faol BOOLEAN DEFAULT TRUE
            )
        """)
        # Materiallar
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id SERIAL PRIMARY KEY,
                nomi TEXT NOT NULL,
                qoldiq REAL DEFAULT 0,
                birlik TEXT NOT NULL,
                asl_birlik TEXT NOT NULL
            )
        """)
        # Qolip formulasi
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS qolip_formula (
                id SERIAL PRIMARY KEY,
                material_id INTEGER,
                miqdor REAL NOT NULL,
                birlik TEXT NOT NULL,
                miqdor_asosiy REAL NOT NULL
            )
        """)
        # Ishlab chiqarish logi
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
        # Sotuv logi
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
        # Tayyor mahsulot
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finished_goods (
                id SERIAL PRIMARY KEY,
                block_type TEXT NOT NULL UNIQUE,
                qoldiq INTEGER DEFAULT 0
            )
        """)
        # Bot sozlamalari
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                id SERIAL PRIMARY KEY,
                kalit TEXT NOT NULL UNIQUE,
                qiymat TEXT NOT NULL
            )
        """)
        # Sozlamalar
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id SERIAL PRIMARY KEY,
                material_id INTEGER,
                min_chegara REAL NOT NULL
            )
        """)
        # Audit log
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
        # Dastlabki tayyor mahsulot
        await conn.execute("""
            INSERT INTO finished_goods (block_type, qoldiq)
            VALUES ('A', 0), ('B', 0)
            ON CONFLICT (block_type) DO NOTHING
        """)
    finally:
        await conn.close()

# ── Foydalanuvchilar ──
async def get_user(user_id):
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id=$1 AND faol=TRUE", user_id
        )
        return dict(row) if row else None
    finally:
        await conn.close()

async def add_user(user_id, ism, username, rol):
    conn = await get_conn()
    try:
        await conn.execute(
            """INSERT INTO users (id, ism, username, rol)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (id) DO UPDATE
               SET ism=$2, username=$3, rol=$4, faol=TRUE""",
            user_id, ism, username, rol
        )
    finally:
        await conn.close()

async def get_all_users():
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            "SELECT * FROM users ORDER BY qoshilgan_vaqt DESC"
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def update_user_rol(user_id, rol):
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE users SET rol=$1 WHERE id=$2", rol, user_id
        )
    finally:
        await conn.close()

async def delete_user(user_id):
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE users SET faol=FALSE WHERE id=$1", user_id
        )
    finally:
        await conn.close()

async def get_pending_users():
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            "SELECT * FROM users WHERE rol='kutish' AND faol=TRUE"
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def superadmin_bormi():
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE rol='superadmin' AND faol=TRUE"
        )
        return row is not None
    finally:
        await conn.close()

# ── Audit log ──
async def add_audit_log(user_id, ism, rol, amal, tafsilot=""):
    conn = await get_conn()
    try:
        await conn.execute(
            """INSERT INTO audit_log (user_id, ism, rol, amal, tafsilot)
               VALUES ($1, $2, $3, $4, $5)""",
            user_id, ism, rol, amal, tafsilot
        )
    finally:
        await conn.close()

async def get_audit_log(limit=50):
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """SELECT * FROM audit_log
               ORDER BY vaqt DESC LIMIT $1""", limit
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()

# ── Materiallar ──
async def get_materials():
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            "SELECT id, nomi, qoldiq, birlik, asl_birlik FROM materials"
        )
        return [tuple(r) for r in rows]
    finally:
        await conn.close()

async def add_material(nomi, qoldiq, birlik):
    qoldiq_asosiy, asosiy_birlik = birlikni_asosiyga(qoldiq, birlik)
    conn = await get_conn()
    try:
        await conn.execute(
            "INSERT INTO materials (nomi, qoldiq, birlik, asl_birlik) VALUES ($1,$2,$3,$4)",
            nomi, qoldiq_asosiy, asosiy_birlik, birlik
        )
    finally:
        await conn.close()

async def update_material_qoldiq(material_id, yangi_qoldiq):
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE materials SET qoldiq=$1 WHERE id=$2",
            yangi_qoldiq, material_id
        )
    finally:
        await conn.close()

async def update_material(material_id, nomi, qoldiq, birlik):
    qoldiq_asosiy, asosiy_birlik = birlikni_asosiyga(qoldiq, birlik)
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE materials SET nomi=$1,qoldiq=$2,birlik=$3,asl_birlik=$4 WHERE id=$5",
            nomi, qoldiq_asosiy, asosiy_birlik, birlik, material_id
        )
    finally:
        await conn.close()

async def delete_material(material_id):
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM qolip_formula WHERE material_id=$1", material_id)
        await conn.execute("DELETE FROM settings WHERE material_id=$1", material_id)
        await conn.execute("DELETE FROM materials WHERE id=$1", material_id)
    finally:
        await conn.close()

async def clear_all_data():
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM materials")
        await conn.execute("DELETE FROM qolip_formula")
        await conn.execute("DELETE FROM production_log")
        await conn.execute("DELETE FROM sales_log")
        await conn.execute("DELETE FROM settings")
        await conn.execute("UPDATE finished_goods SET qoldiq=0")
    finally:
        await conn.close()

# ── Qolip formulasi ──
async def get_qolip_formula():
    conn = await get_conn()
    try:
        rows = await conn.fetch("""
            SELECT m.nomi, q.miqdor, q.birlik, m.qoldiq, m.birlik,
                   m.id, q.miqdor_asosiy, m.asl_birlik
            FROM qolip_formula q
            JOIN materials m ON q.material_id = m.id
        """)
        return [tuple(r) for r in rows]
    finally:
        await conn.close()

async def add_qolip_formula(material_id, miqdor, birlik):
    miqdor_asosiy, _ = birlikni_asosiyga(miqdor, birlik)
    conn = await get_conn()
    try:
        await conn.execute(
            "INSERT INTO qolip_formula (material_id,miqdor,birlik,miqdor_asosiy) VALUES ($1,$2,$3,$4)",
            material_id, miqdor, birlik, miqdor_asosiy
        )
    finally:
        await conn.close()

async def clear_qolip_formula():
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM qolip_formula")
    finally:
        await conn.close()

# ── Ishlab chiqarish ──
async def check_material_yetarli(qolip_soni):
    """Ishlab chiqarishdan oldin materiallar yetarliligini tekshiradi"""
    formula = await get_qolip_formula()
    yetishmaydi = []
    for f in formula:
        nomi = f[0]
        miqdor_asosiy = f[6]
        qoldiq_asosiy = f[3]
        asl_birlik = f[7]
        kerak = miqdor_asosiy * qolip_soni
        if qoldiq_asosiy < kerak:
            bor = asosiydan_birlikga(qoldiq_asosiy, asl_birlik)
            kerak_asl = asosiydan_birlikga(kerak, asl_birlik)
            yetishmaydi.append(
                f"❌ {nomi}: kerak {kerak_asl:.2f} {asl_birlik}, "
                f"bor {bor:.2f} {asl_birlik}"
            )
    return yetishmaydi

async def add_production_log(sana, shablon, qolip_soni, user_id=None):
    conn = await get_conn()
    try:
        await conn.execute(
            "INSERT INTO production_log (sana,shablon,qolip_soni,user_id) VALUES ($1,$2,$3,$4)",
            sana, shablon, qolip_soni, user_id
        )
    finally:
        await conn.close()

async def delete_last_production():
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            "SELECT id FROM production_log ORDER BY id DESC LIMIT 1"
        )
        if row:
            await conn.execute("DELETE FROM production_log WHERE id=$1", row["id"])
            return True
        return False
    finally:
        await conn.close()

async def get_production_by_date(sana):
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            "SELECT shablon, qolip_soni FROM production_log WHERE sana=$1", sana
        )
        return [tuple(r) for r in rows]
    finally:
        await conn.close()

async def get_production_range(boshliq, oxiri):
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            "SELECT sana,shablon,qolip_soni FROM production_log WHERE sana BETWEEN $1 AND $2",
            boshliq, oxiri
        )
        return [tuple(r) for r in rows]
    finally:
        await conn.close()

# ── Sotuv ──
async def add_sales_log(sana, block_type, miqdor, user_id=None):
    """Sotuv kiritadi VA tayyor mahsulot omboridan ayiradi"""
    conn = await get_conn()
    try:
        # Tayyor mahsulot yetarliligini tekshirish
        row = await conn.fetchrow(
            "SELECT qoldiq FROM finished_goods WHERE block_type=$1", block_type
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
        # Sotuv yozuvi + ombor ayirish — bitta tranzaksiyada
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO sales_log (sana,block_type,miqdor,user_id) VALUES ($1,$2,$3,$4)",
                sana, block_type, miqdor, user_id
            )
            await conn.execute(
                "UPDATE finished_goods SET qoldiq=qoldiq-$1 WHERE block_type=$2",
                miqdor, block_type
            )
        return True, "✅ Sotuv kiritildi!"
    finally:
        await conn.close()

async def delete_last_sale():
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            "SELECT id,block_type,miqdor FROM sales_log ORDER BY id DESC LIMIT 1"
        )
        if row:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM sales_log WHERE id=$1", row["id"]
                )
                # Omborga qaytarish
                await conn.execute(
                    "UPDATE finished_goods SET qoldiq=qoldiq+$1 WHERE block_type=$2",
                    row["miqdor"], row["block_type"]
                )
            return True
        return False
    finally:
        await conn.close()

async def get_sales_by_date(sana):
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            "SELECT block_type,miqdor FROM sales_log WHERE sana=$1", sana
        )
        return [tuple(r) for r in rows]
    finally:
        await conn.close()

async def get_sales_range(boshliq, oxiri):
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            "SELECT sana,block_type,miqdor FROM sales_log WHERE sana BETWEEN $1 AND $2",
            boshliq, oxiri
        )
        return [tuple(r) for r in rows]
    finally:
        await conn.close()

# ── Tayyor mahsulot ──
async def get_finished_goods():
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            "SELECT block_type,qoldiq FROM finished_goods ORDER BY block_type"
        )
        return [tuple(r) for r in rows]
    finally:
        await conn.close()

async def set_finished_goods(block_type, qoldiq):
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE finished_goods SET qoldiq=$1 WHERE block_type=$2",
            qoldiq, block_type
        )
    finally:
        await conn.close()

async def update_finished_goods(block_type, delta):
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE finished_goods SET qoldiq=GREATEST(0,qoldiq+$1) WHERE block_type=$2",
            delta, block_type
        )
    finally:
        await conn.close()

# ── Bot sozlamalari ──
async def get_bot_setting(kalit):
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            "SELECT qiymat FROM bot_settings WHERE kalit=$1", kalit
        )
        return row["qiymat"] if row else None
    finally:
        await conn.close()

async def set_bot_setting(kalit, qiymat):
    conn = await get_conn()
    try:
        await conn.execute(
            """INSERT INTO bot_settings (kalit,qiymat) VALUES ($1,$2)
               ON CONFLICT (kalit) DO UPDATE SET qiymat=$2""",
            kalit, qiymat
        )
    finally:
        await conn.close()

# ── Sozlamalar ──
async def get_settings():
    conn = await get_conn()
    try:
        rows = await conn.fetch("""
            SELECT m.nomi, s.min_chegara, m.birlik, m.id
            FROM settings s
            JOIN materials m ON s.material_id = m.id
        """)
        return [tuple(r) for r in rows]
    finally:
        await conn.close()

async def set_min_chegara(material_id, min_chegara):
    conn = await get_conn()
    try:
        await conn.execute(
            """INSERT INTO settings (material_id,min_chegara) VALUES ($1,$2)
               ON CONFLICT (material_id) DO UPDATE SET min_chegara=$2""",
            material_id, min_chegara
        )
    finally:
        await conn.close()
