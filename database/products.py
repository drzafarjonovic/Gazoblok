"""database.products — mahsulotlar, bloklar, shablonlar, tayyor mahsulot,
qolip formulasi va tannarx hisobi (hammasi dinamik, product-aware)."""
from .core import (
    get_pool, _struct_get, _struct_put, _invalidate_struct,
    birlikni_asosiyga, asosiydan_birlikga,
)


# ════════════════════════════════════════════════════════════════════
# MAHSULOTLAR (dinamik)
# ════════════════════════════════════════════════════════════════════
async def get_mahsulotlar(faqat_faol=True):
    key = ("mahsulotlar", faqat_faol)
    c = _struct_get(key)
    if c is not None:
        return c
    pool = await get_pool()
    async with pool.acquire() as conn:
        if faqat_faol:
            rows = await conn.fetch(
                "SELECT * FROM mahsulotlar WHERE faol=TRUE ORDER BY tartib, id")
        else:
            rows = await conn.fetch("SELECT * FROM mahsulotlar ORDER BY tartib, id")
    res = [dict(r) for r in rows]
    _struct_put(key, res)
    return res


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
        pid = await conn.fetchval(
            "INSERT INTO mahsulotlar (kod, nomi, emoji, tartib) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            kod, nomi, emoji, tartib
        )
    _invalidate_struct()
    return pid


async def update_mahsulot(product_id, nomi, emoji):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulotlar SET nomi=$1, emoji=$2 WHERE id=$3",
            nomi, emoji, product_id
        )
    _invalidate_struct()


async def set_mahsulot_ishchi_haqi(product_id, qiymat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulotlar SET ishchi_haqi=$1 WHERE id=$2",
            float(qiymat), product_id
        )
    _invalidate_struct()


async def set_mahsulot_qoshimcha(product_id, qiymat):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulotlar SET qoshimcha_xarajat=$1 WHERE id=$2",
            float(qiymat), product_id
        )
    _invalidate_struct()


async def set_mahsulot_faol(product_id, faol):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulotlar SET faol=$1 WHERE id=$2", bool(faol), product_id
        )
    _invalidate_struct()


async def delete_mahsulot(product_id):
    """Arxivlash (soft-delete) — tarix saqlanadi."""
    await set_mahsulot_faol(product_id, False)


# ════════════════════════════════════════════════════════════════════
# MAHSULOT BLOKLARI
# ════════════════════════════════════════════════════════════════════
async def get_bloklar(product_id):
    key = ("bloklar", product_id)
    c = _struct_get(key)
    if c is not None:
        return c
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM mahsulot_bloklari WHERE product_id=$1 ORDER BY tartib, id",
            product_id
        )
    res = [dict(r) for r in rows]
    _struct_put(key, res)
    return res


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
            await conn.execute(
                "INSERT INTO finished_goods (product_id, block_type, qoldiq) "
                "VALUES ($1,$2,0) ON CONFLICT (product_id, block_type) DO NOTHING",
                product_id, kod
            )
    _invalidate_struct()
    return bid


async def update_blok(blok_id, nomi, olcham, qolip_dona):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulot_bloklari SET nomi=$1, olcham=$2, qolip_dona=$3 WHERE id=$4",
            nomi, olcham, float(qolip_dona), blok_id
        )
    _invalidate_struct()


async def set_blok_sotuv_narx(blok_id, narx):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mahsulot_bloklari SET sotuv_narx=$1 WHERE id=$2",
            float(narx), blok_id
        )
    _invalidate_struct()


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
    _invalidate_struct()


async def delete_blok(blok_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT product_id, kod FROM mahsulot_bloklari WHERE id=$1", blok_id)
            if not row:
                return
            pid, kod = row["product_id"], row["kod"]
            await conn.execute(
                "DELETE FROM shablon_chiqim WHERE block_kod=$1 AND shablon_id IN "
                "(SELECT id FROM shablonlar WHERE product_id=$2)", kod, pid)
            await conn.execute(
                "DELETE FROM finished_goods WHERE product_id=$1 AND block_type=$2", pid, kod)
            await conn.execute(
                "DELETE FROM mahsulot_bloklari WHERE id=$1", blok_id)
    _invalidate_struct()


# ════════════════════════════════════════════════════════════════════
# SHABLONLAR
# ════════════════════════════════════════════════════════════════════
async def get_shablonlar(product_id, faqat_faol=False):
    key = ("shablonlar", product_id, faqat_faol)
    c = _struct_get(key)
    if c is not None:
        return c
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
        # Barcha chiqimlarni BITTA so'rovda olamiz (N+1 oldini olish)
        chiq = await conn.fetch("""
            SELECT sc.shablon_id, sc.block_kod, sc.soni, b.nomi AS blok_nomi
            FROM shablon_chiqim sc
            LEFT JOIN mahsulot_bloklari b
                ON b.product_id=$1 AND b.kod=sc.block_kod
            WHERE sc.shablon_id IN (SELECT id FROM shablonlar WHERE product_id=$1)
            ORDER BY sc.id
        """, product_id)
    by_sh = {}
    for r in chiq:
        by_sh.setdefault(r["shablon_id"], []).append(
            {"block_kod": r["block_kod"], "soni": r["soni"], "blok_nomi": r["blok_nomi"]})
    res = []
    for r in rows:
        d = dict(r)
        d["chiqim"] = by_sh.get(r["id"], [])
        res.append(d)
    _struct_put(key, res)
    return res


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
        sid = await conn.fetchval(
            "INSERT INTO shablonlar (product_id, kod, nomi, tartib) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            product_id, kod, nomi, tartib
        )
    _invalidate_struct()
    return sid


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
    _invalidate_struct()


async def delete_shablon(shablon_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM shablon_chiqim WHERE shablon_id=$1", shablon_id)
            await conn.execute("DELETE FROM shablonlar WHERE id=$1", shablon_id)
    _invalidate_struct()


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
    _invalidate_struct()


async def clear_qolip_formula(product_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM qolip_formula WHERE product_id=$1", product_id)
    _invalidate_struct()


async def set_qolip_formula_item(product_id, material_id, miqdor, birlik):
    """Bitta material uchun formula qiymatini o'rnatadi (upsert)."""
    miqdor_asosiy, _ = birlikni_asosiyga(miqdor, birlik)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM qolip_formula WHERE product_id=$1 AND material_id=$2",
                product_id, material_id)
            await conn.execute(
                "INSERT INTO qolip_formula (product_id, material_id, miqdor, birlik, miqdor_asosiy) "
                "VALUES ($1,$2,$3,$4,$5)",
                product_id, material_id, miqdor, birlik, miqdor_asosiy)
    _invalidate_struct()


async def remove_qolip_formula_item(product_id, material_id):
    """Materialni formuladan olib tashlaydi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM qolip_formula WHERE product_id=$1 AND material_id=$2",
            product_id, material_id)
    _invalidate_struct()


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
    """{(product_id, block_kod): tannarx_uzs} — barcha mahsulotlar (COGS uchun).
    To'plamli so'rovlar + struktura keshi (narx/struktura o'zgarsa invalidatsiya)."""
    cached = _struct_get(("tannarx_map",))
    if cached is not None:
        return dict(cached)
    pool = await get_pool()
    async with pool.acquire() as conn:
        mat_rows = await conn.fetch("""
            SELECT q.product_id,
                   COALESCE(SUM(q.miqdor_asosiy * COALESCE(m.narx, 0)), 0) AS mat
            FROM qolip_formula q
            JOIN materials m ON q.material_id = m.id
            GROUP BY q.product_id
        """)
        prod_rows = await conn.fetch(
            "SELECT id, ishchi_haqi, qoshimcha_xarajat FROM mahsulotlar")
        blk_rows = await conn.fetch(
            "SELECT product_id, kod, qolip_dona, tannarx_override FROM mahsulot_bloklari")
    mat = {r["product_id"]: float(r["mat"]) for r in mat_rows}
    qolip = {}
    for r in prod_rows:
        qolip[r["id"]] = (mat.get(r["id"], 0.0)
                          + float(r["ishchi_haqi"] or 0)
                          + float(r["qoshimcha_xarajat"] or 0))
    natija = {}
    for b in blk_rows:
        pid = b["product_id"]
        dona = b["qolip_dona"] or 0
        auto = (qolip.get(pid, 0.0) / dona) if dona else 0.0
        over = b["tannarx_override"]
        natija[(pid, b["kod"])] = float(over) if over is not None else auto
    _struct_put(("tannarx_map",), natija)
    return dict(natija)
