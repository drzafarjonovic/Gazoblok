"""database.materials — xom ashyo ombori, minimum chegara, material narxlari."""
from .core import get_pool, birlikni_asosiyga, _invalidate_struct


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
    _invalidate_struct()


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
    _invalidate_struct()  # tannarx_map material narxiga bog'liq
