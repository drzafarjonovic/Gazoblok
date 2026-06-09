import aiosqlite

DB_NAME = "gazobot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Materiallar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nomi TEXT NOT NULL,
                qoldiq REAL DEFAULT 0,
                birlik TEXT NOT NULL
            )
        """)
        # Qolip formulasi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS qolip_formula (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER,
                miqdor REAL NOT NULL,
                birlik TEXT NOT NULL,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
        """)
        # Ishlab chiqarish logi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS production_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sana TEXT NOT NULL,
                shablon INTEGER NOT NULL,
                qolip_soni INTEGER NOT NULL
            )
        """)
        # Sotuv logi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sales_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sana TEXT NOT NULL,
                block_type TEXT NOT NULL,
                miqdor INTEGER NOT NULL
            )
        """)
        # Sozlamalar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER,
                min_chegara REAL NOT NULL,
                FOREIGN KEY (material_id) REFERENCES materials(id)
            )
        """)
        await db.commit()

async def get_materials():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM materials") as cursor:
            return await cursor.fetchall()

async def add_material(nomi, qoldiq, birlik):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO materials (nomi, qoldiq, birlik) VALUES (?, ?, ?)",
            (nomi, qoldiq, birlik)
        )
        await db.commit()

async def update_material_qoldiq(material_id, yangi_qoldiq):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE materials SET qoldiq = ? WHERE id = ?",
            (yangi_qoldiq, material_id)
        )
        await db.commit()

async def get_qolip_formula():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT m.nomi, q.miqdor, q.birlik, m.qoldiq, m.birlik, m.id
            FROM qolip_formula q
            JOIN materials m ON q.material_id = m.id
        """) as cursor:
            return await cursor.fetchall()

async def add_qolip_formula(material_id, miqdor, birlik):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO qolip_formula (material_id, miqdor, birlik) VALUES (?, ?, ?)",
            (material_id, miqdor, birlik)
        )
        await db.commit()

async def clear_qolip_formula():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM qolip_formula")
        await db.commit()

async def add_production_log(sana, shablon, qolip_soni):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO production_log (sana, shablon, qolip_soni) VALUES (?, ?, ?)",
            (sana, shablon, qolip_soni)
        )
        await db.commit()

async def add_sales_log(sana, block_type, miqdor):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO sales_log (sana, block_type, miqdor) VALUES (?, ?, ?)",
            (sana, block_type, miqdor)
        )
        await db.commit()

async def get_production_by_date(sana):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT shablon, qolip_soni FROM production_log WHERE sana = ?",
            (sana,)
        ) as cursor:
            return await cursor.fetchall()

async def get_sales_by_date(sana):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT block_type, miqdor FROM sales_log WHERE sana = ?",
            (sana,)
        ) as cursor:
            return await cursor.fetchall()

async def get_production_range(boshliq, oxiri):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT sana, shablon, qolip_soni FROM production_log WHERE sana BETWEEN ? AND ?",
            (boshliq, oxiri)
        ) as cursor:
            return await cursor.fetchall()

async def get_sales_range(boshliq, oxiri):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT sana, block_type, miqdor FROM sales_log WHERE sana BETWEEN ? AND ?",
            (boshliq, oxiri)
        ) as cursor:
            return await cursor.fetchall()

async def get_settings():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT m.nomi, s.min_chegara, m.birlik, m.id
            FROM settings s
            JOIN materials m ON s.material_id = m.id
        """) as cursor:
            return await cursor.fetchall()

async def set_min_chegara(material_id, min_chegara):
    async with aiosqlite.connect(DB_NAME) as db:
        existing = await db.execute(
            "SELECT id FROM settings WHERE material_id = ?", (material_id,)
        )
        row = await existing.fetchone()
        if row:
            await db.execute(
                "UPDATE settings SET min_chegara = ? WHERE material_id = ?",
                (min_chegara, material_id)
            )
        else:
            await db.execute(
                "INSERT INTO settings (material_id, min_chegara) VALUES (?, ?)",
                (material_id, min_chegara)
            )
        await db.commit()
