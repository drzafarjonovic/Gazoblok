"""
Sozlamalar bo'limi — aggregator.

Ilgari bu fayl 1600+ qatorli edi (material + mahsulot + tizim hammasi birga).
Endi u uchta mavzuli modulga bo'lingan:
  • settings_materials.py — material CRUD, minimum chegara
  • settings_products.py  — mahsulot/blok/shablon/formula
  • settings_system.py    — hisobot jadvali, obunachilar, PIN, til, tozalash

Bu fayl faqat top-level menyu handlerlarini saqlaydi va sub-routerlarni
birlashtiradi. `router` bot.py da o'zgarishsiz ishlatiladi.
"""
from aiogram import Router
from aiogram.types import Message
from translation import Tkey, say
from .settings_common import sozlamalar_menu, faqat_superadmin as _faqat_superadmin
from . import settings_materials, settings_products, settings_system

router = Router()
router.include_router(settings_materials.router)
router.include_router(settings_products.router)
router.include_router(settings_system.router)


@router.message(Tkey("⚙️ Sozlamalar"))
async def sozlamalar(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await say(message, "⚙️ Sozlamalar bo'limi:",
              reply_markup=await sozlamalar_menu(message.from_user.id))


@router.message(Tkey("⬅️ Sozlamalar"))
async def orqaga_sozlamalar(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await say(message, "⚙️ Sozlamalar bo'limi:",
              reply_markup=await sozlamalar_menu(message.from_user.id))
