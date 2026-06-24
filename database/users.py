"""database.users — foydalanuvchilar, rol/permission, audit, lifecycle, PIN, stats."""
import time
from .core import (
    get_pool,
    _perm_cache, _PERM_TTL,
    _user_cache, _USER_TTL, _invalidate_user,
    _touch_ts, _TOUCH_INTERVAL,
)


# ── Permissions ──
async def get_user_permissions(user_id, rol):
    now = time.monotonic()
    hit = _perm_cache.get(user_id)
    if hit and hit[2] == rol and now - hit[1] < _PERM_TTL:
        return dict(hit[0])
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
    _perm_cache[user_id] = (perms, now, rol)
    return dict(perms)


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
    _perm_cache.clear()  # rol o'zgarishi barcha shu roldagilarga ta'sir qiladi


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
    _perm_cache.pop(user_id, None)


async def clear_user_permissions(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_permissions WHERE user_id=$1", user_id
        )
    _perm_cache.pop(user_id, None)


async def has_permission(user_id, rol, permission):
    perms = await get_user_permissions(user_id, rol)
    return perms.get(permission, False)


# ── Foydalanuvchilar ──
async def get_user(user_id):
    now = time.monotonic()
    hit = _user_cache.get(user_id)
    if hit and now - hit[1] < _USER_TTL:
        return dict(hit[0]) if hit[0] is not None else None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id=$1 AND faol=TRUE", user_id
        )
    d = dict(row) if row else None
    _user_cache[user_id] = (d, now)
    return dict(d) if d is not None else None


async def add_user(user_id, ism, username, rol):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (id, ism, username, rol)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE
            SET ism=$2, username=$3, rol=$4, faol=TRUE
        """, user_id, ism, username, rol)
    _invalidate_user(user_id)


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
    _invalidate_user(user_id)


async def delete_user(user_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET faol=FALSE WHERE id=$1", user_id
        )
    _invalidate_user(user_id)


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
    _invalidate_user(user_id)


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
    _invalidate_user(user_id)


async def update_user_username(user_id, username):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET username=$1 WHERE id=$2", username, user_id)
    _invalidate_user(user_id)


async def touch_user(user_id):
    # Yozuvni cheklaymiz: har bir xabarda emas, eng ko'pi bilan _TOUCH_INTERVAL da bir marta
    now = time.monotonic()
    last = _touch_ts.get(user_id)
    if last is not None and now - last < _TOUCH_INTERVAL:
        return
    _touch_ts[user_id] = now
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET oxirgi_faollik=NOW() WHERE id=$1 AND faol=TRUE", user_id)


async def update_user_til(user_id: int, til: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET til=$1 WHERE id=$2", til, user_id)
    _invalidate_user(user_id)


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


# ── PIN qulf holati (restartga chidamli) ──
async def get_pin_active(user_id):
    """Foydalanuvchining oxirgi PIN-faollik epoch'i (yoki None)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT last_active FROM pin_holat WHERE user_id=$1", user_id)
        return row["last_active"] if row else None


async def set_pin_active(user_id, epoch):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO pin_holat (user_id, last_active) VALUES ($1,$2)
            ON CONFLICT (user_id) DO UPDATE SET last_active=$2
        """, user_id, float(epoch))


async def clear_pin_active(user_id=None):
    """PIN o'rnatilganda/o'chirilganda qulf holatini tozalash."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if user_id is None:
            await conn.execute("DELETE FROM pin_holat")
        else:
            await conn.execute("DELETE FROM pin_holat WHERE user_id=$1", user_id)
