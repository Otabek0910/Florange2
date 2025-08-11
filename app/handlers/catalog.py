from aiogram import Router, types, F
from sqlalchemy import select
from app.database import get_session
from app.models import Category, Product

router = Router()

# Показываем список категорий
@router.message(F.text == "🛍 Каталог")
async def show_categories(message: types.Message):
    async for session in get_session():
        result = await session.execute(select(Category))
        categories = result.scalars().all()

    if not categories:
        await message.answer("Категорий пока нет.")
        return

    kb = types.InlineKeyboardMarkup()
    for cat in categories:
        kb.add(types.InlineKeyboardButton(text=cat.name, callback_data=f"cat_{cat.id}"))

    await message.answer("Выберите категорию:", reply_markup=kb)

# Показываем товары в категории
@router.callback_query(F.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])

    async for session in get_session():
        result = await session.execute(select(Product).where(Product.category_id == cat_id))
        products = result.scalars().all()

    if not products:
        await callback.message.answer("В этой категории пока нет товаров.")
        await callback.answer()
        return

    for product in products:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(text=f"Добавить в корзину", callback_data=f"add_{product.id}"))

        await callback.message.answer_photo(
            photo=product.photo_file_id or "https://via.placeholder.com/300",
            caption=f"<b>{product.name}</b>\n{product.description}\nЦена: {product.price} сум",
            reply_markup=kb
        )

    await callback.answer()
