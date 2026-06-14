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

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            statement_cache_size=0,
            min_size=2,
            max_size=10
        )
    return _pool

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
        await conn.execute("DELETE FROM materials")
        await conn.execute("DELETE FROM qolip_formula")
        await conn.execute("DELETE FROM production_log")
        await conn.execute("DELETE FROM sales_log")
        await conn.execute("DELETE FROM settings")
        await conn.execute("DELETE FROM material_chiqim_log")
        await conn.execute("DELETE FROM inventarizatsiya")
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
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO material_chiqim_log
            (production_log_id, material_id, material_nomi, ketgan_miqdor, birlik, sana)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, production_log_id, material_id, material_nomi, ketgan_miqdor, birlik, sana)

async def get_material_chiqim_range(boshliq, oxiri):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT material_nomi, SUM(ketgan_miqdor) as jami, birlik, sana
            FROM material_chiqim_log
            WHERE sana BETWEEN $1 AND $2
            GROUP BY material_nomi, birlik, sana
            ORDER BY sana
        """, boshliq, oxiri)
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
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO production_log (sana, shablon, qolip_soni, user_id)
            VALUES ($1, $2, $3, $4) RETURNING id
        """, sana, shablon, qolip_soni, user_id)
        return row["id"]

async def delete_last_production_with_restore():
    """Oxirgi ishlab chiqarishni o'chirib, materiallarni omborga qaytaradi"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Oxirgi yozuv
        row = await conn.fetchrow(
            "SELECT id, shablon, qolip_soni, sana FROM production_log ORDER BY id DESC LIMIT 1"
        )
        if not row:
            return False, "❌ O'chiriladigan yozuv yo'q!"

        prod_id = row["id"]
        shablon = row["shablon"]
        qolip_soni = row["qolip_soni"]

        # Shu yozuvga tegishli chiqim loglarini topish
        chiqim_logs = await conn.fetch("""
            SELECT material_id, material_nomi, ketgan_miqdor, birlik
            FROM material_chiqim_log
            WHERE production_log_id=$1
        """, prod_id)

        # Bloklar hisobi (tayyor ombordan ayirish)
        if shablon == 1:
            A_blok = qolip_soni * 12
            B_blok = 0
        elif shablon == 2:
            A_blok = 0
            B_blok = qolip_soni * 24
        else:
            A_blok = qolip_soni * 11
            B_blok = qolip_soni * 2

        # Tayyor ombordan ayirish
        if A_blok > 0:
            await conn.execute("""
                UPDATE finished_goods
                SET qoldiq = GREATEST(0, qoldiq - $1)
                WHERE block_type='A'
            """, A_blok)
        if B_blok > 0:
            await conn.execute("""
                UPDATE finished_goods
                SET qoldiq = GREATEST(0, qoldiq - $1)
                WHERE block_type='B'
            """, B_blok)

        # Materiallarni omborga qaytarish
        qaytarilgan = []
        for ch in chiqim_logs:
            material_id = ch["material_id"]
            ketgan = ch["ketgan_miqdor"]
            nomi = ch["material_nomi"]
            birlik = ch["birlik"]

            await conn.execute("""
                UPDATE materials SET qoldiq = qoldiq + $1 WHERE id = $2
            """, ketgan, material_id)

            asl_birlik_row = await conn.fetchrow(
                "SELECT asl_birlik FROM materials WHERE id=$1", material_id
            )
            if asl_birlik_row:
                asl_birlik = asl_birlik_row["asl_birlik"]
                qaytarilgan_asl = asosiydan_birlikga(ketgan, asl_birlik)
                qaytarilgan.append(
                    f"   {nomi}: +{qaytarilgan_asl:.2f} {asl_birlik}"
                )

        # Chiqim loglarini o'chirish
        await conn.execute(
            "DELETE FROM material_chiqim_log WHERE production_log_id=$1", prod_id
        )
        # Ishlab chiqarish yozuvini o'chirish
        await conn.execute(
            "DELETE FROM production_log WHERE id=$1", prod_id
        )

        tafsilot = f"Shablon {shablon}, {qolip_soni} qolip o'chirildi"
        if qaytarilgan:
            tafsilot += "\nOmborga qaytarildi:\n" + "\n".join(qaytarilgan)
        else:
            tafsilot += "\n(Chiqim tarixi topilmadi, materiallar qaytarilmadi)"

        return True, tafsilot

async def get_production_by_date(sana):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT shablon, qolip_soni FROM production_log WHERE sana=$1", sana
        )
        return [tuple(r) for r in rows]

async def get_production_range(boshliq, oxiri):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sana, shablon, qolip_soni
            FROM production_log
            WHERE sana BETWEEN $1 AND $2
            ORDER BY sana
        """, boshliq, oxiri)
        return [tuple(r) for r in rows]

async def get_production_detail_range(boshliq, oxiri):
    """Foydalanuvchi bilan to'liq ishlab chiqarish tarixi"""
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
        """, boshliq, oxiri)
        return [dict(r) for r in rows]

# ── Sotuv ──
async def add_sales_log(sana, block_type, miqdor, user_id=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
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
        await conn.execute(
            "INSERT INTO sales_log (sana,block_type,miqdor,user_id) VALUES ($1,$2,$3,$4)",
            sana, block_type, miqdor, user_id
        )
        await conn.execute(
            "UPDATE finished_goods SET qoldiq=qoldiq-$1 WHERE block_type=$2",
            miqdor, block_type
        )
        return True, "✅ Sotuv kiritildi!"

async def delete_last_sale():
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, block_type, miqdor FROM sales_log ORDER BY id DESC LIMIT 1"
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
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT block_type, miqdor FROM sales_log WHERE sana=$1", sana
        )
        return [tuple(r) for r in rows]

async def get_sales_range(boshliq, oxiri):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sana, block_type, miqdor
            FROM sales_log
            WHERE sana BETWEEN $1 AND $2
            ORDER BY sana
        """, boshliq, oxiri)
        return [tuple(r) for r in rows]

async def get_sales_detail_range(boshliq, oxiri):
    """Foydalanuvchi bilan to'liq sotuv tarixi"""
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
        """, boshliq, oxiri)
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
    farq = real_hisob - bot_hisob
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO inventarizatsiya
            (sana, block_type, bot_hisob, real_hisob, farq, izoh, user_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, sana, block_type, bot_hisob, real_hisob, farq, izoh, user_id)
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
