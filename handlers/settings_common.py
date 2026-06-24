"""
Sozlamalar bo'limi uchun umumiy yordamchilar (materials/products/system
modullari o'rtasida bo'lishiladi).
"""
from aiogram.types import Message, CallbackQuery
import database as db
from translation import say, build_keyboard


async def sozlamalar_menu(user_id):
    return await build_keyboard(user_id, [
        ["🏭 Mahsulot boshqaruvi"],
        ["📦 Materiallar"],
        ["💵 Narxlar va valyuta"],
        ["⚙️ Tizim sozlamalari"],
        ["🏠 Asosiy menyu"],
    ])


async def faqat_superadmin(message: Message, user=None) -> bool:
    """Sozlamalar — 'sozlama_boshqaruv' huquqi (superadmin doim ega)."""
    if user is None:
        user = await db.get_user(message.from_user.id)
    if not user or not user["faol"]:
        await say(message, "❌ Ruxsat yo'q!")
        return False
    if await db.has_permission(message.from_user.id, user["rol"], "sozlama_boshqaruv"):
        return True
    await say(message, "❌ Sizda sozlamalarni boshqarish huquqi yo'q!")
    return False


async def cb_ok(callback: CallbackQuery) -> bool:
    user = await db.get_user(callback.from_user.id)
    if not user or not user["faol"]:
        await callback.answer("❌", show_alert=True)
        return False
    if user["rol"] == "superadmin" or await db.has_permission(
            callback.from_user.id, user["rol"], "sozlama_boshqaruv"):
        return True
    await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
    return False
