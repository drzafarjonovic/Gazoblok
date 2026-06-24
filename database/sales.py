"""database.sales — sotuv (atomik) va inventarizatsiya (product-aware)."""
from .core import get_pool, bugungi_sana


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
