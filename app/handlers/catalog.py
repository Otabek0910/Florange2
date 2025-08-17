from aiogram import Router, types, F

from app.database.database import get_session
from app.services import UserService, CatalogService
from app.translate import t
from app.handlers.common import get_user_lang

router = Router()

async def _get_user_and_lang(session, tg_id: int):
    """Получить пользователя и язык через сервис"""
    user_service = UserService(session)
    try:
        user = await user_service.get_user_by_tg_id(str(tg_id))
        return user, get_user_lang(user)
    except:
        return None, "ru"

@router.callback_query(F.data == "open_catalog")
async def show_categories(callback: types.CallbackQuery):
    """Показать список категорий"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        catalog_service = CatalogService(session)
        
        categories = await catalog_service.get_categories()

    if not categories:
        await callback.message.edit_text(t(lang, "no_categories"))
        await callback.answer()
        return

    # Создаем кнопки категорий с учетом языка
    kb_rows = []
    for category in categories:
        cat_name = category.name_ru if lang == "ru" else category.name_uz
        kb_rows.append([types.InlineKeyboardButton(
            text=cat_name, 
            callback_data=f"cat_{category.id}"
        )])
    
    # Добавляем кнопку назад
    kb_rows.append([types.InlineKeyboardButton(
        text=t(lang, "back_to_menu"), 
        callback_data="main_menu"
    )])
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(t(lang, "choose_category"), reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    """Показать товары в выбранной категории"""
    cat_id = int(callback.data.split("_")[1])

    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        catalog_service = CatalogService(session)
        
        # Получаем товары категории
        products = await catalog_service.get_products_by_category(cat_id)
        
        # Получаем категорию для названия
        categories = await catalog_service.get_categories()
        category = next((cat for cat in categories if cat.id == cat_id), None)
        cat_name = category.name_ru if lang == "ru" else category.name_uz if category else "Категория"

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

async def show_product_card(callback: types.CallbackQuery, products, index, cat_id, lang):
    """Показать карточку товара"""
    product = products[index]
    
    # Формируем текст карточки (твоя логика)
    total = len(products)
    currency = t(lang, "currency")
    name = product.name_ru if lang == "ru" else product.name_uz
    desc = (product.desc_ru if lang == "ru" else product.desc_uz) or ""
    
    text = f"🛍 <b>{name}</b>\n\n{desc}\n\n💰 {product.price} {currency}"
    text += f"\n\n📊 {index + 1} из {total}"
    
    # Создаем клавиатуру навигации (твоя логика)
    total = len(products)
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
        [types.InlineKeyboardButton(text="🛒 К оформлению заказа", callback_data="goto_checkout")],  # ПРОСТАЯ КНОПКА
        [types.InlineKeyboardButton(text=t(lang, "back_to_categories"), callback_data="open_catalog")]
    ])

    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    try:
        # Пытаемся отправить фото (если есть)
        if hasattr(product, 'photo_url') and product.photo_url:
            await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=product.photo_url,
                caption=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            # Удаляем предыдущее сообщение
            try:
                await callback.message.delete()
            except:
                pass
        else:
            # Нет фото - редактируем текущее сообщение
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        print(f"Photo error: {e}")
        # Fallback: всегда редактируем текст без фото
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception as edit_error:
            print(f"Edit error: {edit_error}")
            # Last fallback: отправляем новое сообщение
            try:
                await callback.message.delete()
            except:
                pass
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML"
            )

@router.callback_query(F.data.startswith("prod_"))
async def navigate_products(callback: types.CallbackQuery):
    """Навигация по товарам в категории"""
    parts = callback.data.split("_")
    cat_id = int(parts[1])
    index = int(parts[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        catalog_service = CatalogService(session)
        
        # Получаем товары заново (TODO: добавить кэширование)
        products = await catalog_service.get_products_by_category(cat_id)
    
    if not products or index >= len(products):
        await callback.answer("Товар не найден")
        return
        
    await show_product_card(callback, products, index, cat_id, lang)
    await callback.answer()

@router.callback_query(F.data == "goto_checkout")
async def goto_checkout(callback: types.CallbackQuery, user=None):
    """Переход к оформлению заказа"""
    if not user:
        await callback.answer("Пользователь не найден")
        return
    
    lang = user.lang or "ru"
    
    # Проверяем корзину
    from app.utils.cart import get_cart
    cart_data = get_cart(callback.from_user.id)
    
    if not cart_data:
        await callback.answer("🛒 Корзина пуста! Добавьте товары перед оформлением.", show_alert=True)
        return
    
    # Показываем корзину с кнопкой оформления
    from app.handlers.cart import show_cart
    await show_cart(callback)