"""Foydalanuvchiga telefon + parol o'rnatish (mobil ilovaga kirish uchun).

Ishlatish:
  python -m webapi.set_password list
  python -m webapi.set_password set <user_id> <telefon> <parol>

Misol:
  python -m webapi.set_password set 8937512952 +998901234567 MyParol123
"""
import sys
import asyncio

import database as db
from database.core import get_pool
from webapi import auth


async def _ensure_columns():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS telefon TEXT")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS parol_hash TEXT")


async def list_users():
    await _ensure_columns()
    users = await db.get_all_users()
    print(f"{'ID':<14} {'Ism':<20} {'Rol':<12} Telefon")
    print("-" * 62)
    for u in users:
        print(
            f"{u['id']:<14} {(u.get('ism') or ''):<20} "
            f"{(u.get('rol') or ''):<12} {u.get('telefon') or '—'}"
        )


async def set_password(user_id, telefon, parol):
    await _ensure_columns()
    ph = auth.hash_password(parol)
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE users SET telefon=$1, parol_hash=$2 WHERE id=$3",
            telefon.strip(), ph, int(user_id),
        )
    count = int(res.split()[-1]) if res else 0
    if count == 0:
        print("❌ Bunday ID li foydalanuvchi topilmadi. Avval 'list' bilan tekshiring.")
    else:
        print(f"✅ Tayyor! Endi {telefon} + parol bilan ilovaga kirish mumkin.")


def main():
    args = sys.argv[1:]
    if args and args[0] == "list":
        asyncio.run(list_users())
    elif len(args) == 4 and args[0] == "set":
        asyncio.run(set_password(args[1], args[2], args[3]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
