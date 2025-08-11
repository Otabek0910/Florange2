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

    # FIXED: Использовать правильные поля
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text=cat.name_ru if lang == "ru" else cat.name_uz, 
            callback_data=f"cat_{cat.id}"
        )]
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
        
        # Получаем товары
        result = await session.execute(select(Product).where(
            Product.category_id == cat_id, 
            Product.is_active == True
        ))
        products = result.scalars().all()
        
        # Получаем название категории
        category = await session.get(Category, cat_id)
        cat_name = category.name_ru if lang == "ru" else category.name_uz

    if not products:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=t(lang, "back_to_categories"), callback_data="open_catalog")]
        ])
        await callback.message.edit_text(
            f"📂 {cat_name}\n\n{t(lang, 'no_products')}", 
            reply_markup=kb
        )
        await callback.answer()
        return

    # Показываем первый товар
    await show_product_card(callback, products, 0, cat_id, lang)

async def show_product_card(callback: types.CallbackQuery, products: list, index: int, cat_id: int, lang: str):
    """Показать карточку товара с навигацией"""
    product = products[index]
    total = len(products)
    
    # Формируем текст карточки
    currency = t(lang, "currency")
    name = product.name_ru if lang == "ru" else product.name_uz
    desc = (product.desc_ru if lang == "ru" else product.desc_uz) or ""
    
    text = f"🛍 <b>{name}</b>\n\n{desc}\n\n💰 {product.price} {currency}"
    text += f"\n\n📊 {index + 1} из {total}"
    
    # Кнопки навигации и действий
    kb_rows = []
    
    # Навигация
    nav_row = []
    if index > 0:
        nav_row.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"prod_{cat_id}_{index-1}"))
    if index < total - 1:
        nav_row.append(types.InlineKeyboardButton(text="➡️", callback_data=f"prod_{cat_id}_{index+1}"))
    
    if nav_row:
        kb_rows.append(nav_row)
    
    # Действия
    kb_rows.extend([
        [types.InlineKeyboardButton(text=t(lang, "add_to_cart"), callback_data=f"add_{product.id}")],
        [types.InlineKeyboardButton(text=t(lang, "back_to_categories"), callback_data="open_catalog")]
    ])
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    # Отправляем фото или текст
    photo_url = product.photo_url or "https://via.placeholder.com/400x300/FFB6C1/000000?text=🌸"
    
    try:
        if callback.message.photo:
            # Если уже есть фото, редактируем подпись
            await callback.message.edit_caption(caption=text, reply_markup=kb)
        else:
            # Если текстовое сообщение, отправляем новое с фото
            await callback.message.delete()
            await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo_url,
                caption=text,
                reply_markup=kb
            )
    except Exception:
        # Fallback на текст
        await callback.message.edit_text(text, reply_markup=kb)

# Добавить обработчик навигации по товарам
@router.callback_query(F.data.startswith("prod_"))
async def navigate_products(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    cat_id = int(parts[1])
    index = int(parts[2])
    
    async for session in get_session():
        lang = await _get_user_lang(session, callback.from_user.id)
        
        # Получаем товары заново (кэширование позже)
        result = await session.execute(select(Product).where(
            Product.category_id == cat_id,
            Product.is_active == True
        ))
        products = result.scalars().all()
    
    await show_product_card(callback, products, index, cat_id, lang)
    await callback.answer()