"""database.reports — hisobot agregatlari (product-aware) va hisobot obunachilari."""
from .core import get_pool


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
