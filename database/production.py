"""database.production — ishlab chiqarish (atomik, product-aware)."""
from .core import get_pool, bugungi_sana, asosiydan_birlikga


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
        srows = await conn.fetch("""
            SELECT s.nomi AS shablon_nomi, s.tartib AS tartib,
                   COALESCE(SUM(p.qolip_soni),0) AS qty
            FROM production_log p
            LEFT JOIN shablonlar s ON p.shablon_id=s.id
            WHERE p.product_id=$1 AND p.sana=$2
            GROUP BY s.nomi, s.tartib
            ORDER BY s.tartib
        """, product_id, bugun)
        brows = await conn.fetch("""
            SELECT b.nomi AS blok_nomi, sc.block_kod AS kod,
                   COALESCE(SUM(sc.soni * p.qolip_soni),0) AS soni
            FROM production_log p
            JOIN shablon_chiqim sc ON sc.shablon_id = p.shablon_id
            LEFT JOIN mahsulot_bloklari b
                ON b.product_id = p.product_id AND b.kod = sc.block_kod
            WHERE p.product_id=$1 AND p.sana=$2
            GROUP BY b.nomi, sc.block_kod
        """, product_id, bugun)
    jami_qolip = sum(int(r["qty"]) for r in srows)
    shablonlar = [{"nomi": r["shablon_nomi"] or "?", "soni": int(r["qty"])} for r in srows]
    bloklar = {(r["blok_nomi"] or r["kod"]): int(r["soni"]) for r in brows}
    return {"jami_qolip": jami_qolip, "shablonlar": shablonlar, "bloklar": bloklar}
