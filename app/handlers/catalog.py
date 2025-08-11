from aiogram import Router, types, F
from sqlalchemy import select
from decimal import Decimal

from app.database import get_session
from app.models import Category, Product, User
from app.translate import t

router = Router()

async def _get_user_lang(session, tg_id: int) -> str:
    res = await session.execute(select(User).where(User.tg_id == str(tg_id)))
    user = res.scalars().first()
    return (user.lang or "ru") if user else "ru"

# Открыть список категорий
@router.callback_query(F.data == "open_catalog")
async def show_categories(callback: types.CallbackQuery):
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        result = await session.execute(select(Category))
        categories = result.scalars().all()

    if not categories:
        await callback.message.edit_text(t(lang, "no_categories"))
        await callback.answer()
        return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=cat.name, callback_data=f"cat_{cat.id}")]
        for cat in categories
    ])
    await callback.message.edit_text(t(lang, "choose_category"), reply_markup=kb)
    await callback.answer()

# Показать товары в выбранной категории
@router.callback_query(F.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])

    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        result = await session.execute(select(Product).where(Product.category_id == cat_id, Product.is_active == True))
        products = result.scalars().all()

    if not products:
        await callback.message.answer(t(lang, "no_products"))
        await callback.answer()
        return

    currency = t(lang, "currency")
    for product in products:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "add_to_cart"), callback_data=f"add_{product.id}")],
        ])

        price = product.price if isinstance(product.price, (int, float, Decimal)) else 0
        caption = t(
            lang,
            "product_card_caption",
            name=product.name,
            desc=(product.description or ""),
            price=price,
            currency=currency,
        )

        await callback.message.answer_photo(
            product.photo_file_id or "https://via.placeholder.com/300",
            caption=caption,
            reply_markup=kb
        )

    await callback.answer()
