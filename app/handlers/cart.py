from aiogram import Router, types, F
from decimal import Decimal

from app.database import get_session
from app.services import UserService, CatalogService
from app.utils.cart import add_to_cart, get_cart, clear_cart
from app.translate import t
from app.exceptions import ProductNotFoundError

router = Router()

async def _get_user_and_lang(session, tg_id: int):
    """Получить пользователя и язык через сервис"""
    user_service = UserService(session)
    try:
        user = await user_service.get_user_by_tg_id(str(tg_id))
        return user, user.lang or "ru"
    except:
        return None, "ru"

@router.callback_query(F.data.startswith("add_"))
async def add_product(callback: types.CallbackQuery):
    """Добавить товар в корзину"""
    product_id = int(callback.data.split("_")[1])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        catalog_service = CatalogService(session)
        
        try:
            # Проверяем существование и активность товара
            product = await catalog_service.get_product(product_id)
            
            # Добавляем в корзину
            add_to_cart(callback.from_user.id, product_id)
            
            await callback.answer(t(lang, "item_added"), show_alert=False)
            
        except ProductNotFoundError:
            await callback.answer(t(lang, "product_not_found"), show_alert=True)

@router.callback_query(F.data == "open_cart")
async def show_cart(callback: types.CallbackQuery):
    """Показать содержимое корзины"""
    cart_data = get_cart(callback.from_user.id)

    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        catalog_service = CatalogService(session)

        if not cart_data:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
            ])
            await callback.message.edit_text(t(lang, "cart_empty"), reply_markup=kb)
            await callback.answer()
            return

        lines = [t(lang, "cart_title"), ""]
        total = Decimal("0")
        invalid_items = []

        # Обрабатываем каждый товар в корзине
        for pid, qty in cart_data.items():
            try:
                product = await catalog_service.get_product(int(pid))
                price = Decimal(str(product.price))
                name = product.name_ru if lang == "ru" else product.name_uz
                
                line_total = price * Decimal(str(qty))
                lines.append(f"{name} — {qty} × {price} {t(lang, 'currency')} = {line_total} {t(lang, 'currency')}")
                total += line_total
                
            except ProductNotFoundError:
                # Товар больше не существует или неактивен
                invalid_items.append(pid)
                continue

        # Удаляем недействительные товары из корзины
        for invalid_pid in invalid_items:
            from app.utils.cart import remove_from_cart
            # Удаляем полностью
            cart_data_current = get_cart(callback.from_user.id)
            if invalid_pid in cart_data_current:
                qty_to_remove = cart_data_current[invalid_pid]
                for _ in range(qty_to_remove):
                    remove_from_cart(callback.from_user.id, int(invalid_pid))

        if not lines[2:]:  # Если после очистки корзина пуста
            await callback.message.edit_text(t(lang, "cart_empty"))
            await callback.answer()
            return

        # Добавляем итого
        lines.append("")
        lines.append(f"<b>{t(lang, 'total_line', total=total, currency=t(lang, 'currency'))}</b>")
        
        if invalid_items:
            lines.append(f"\n⚠️ {len(invalid_items)} товар(ов) удалено (более недоступны)")

        text = "\n".join(lines)

    # Кнопки действий
    kb_rows = [
        [types.InlineKeyboardButton(text=t(lang, "cart_clear"), callback_data="clear_cart")],
        [types.InlineKeyboardButton(text=t(lang, "cart_checkout"), callback_data="checkout")],
        [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
    ]
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "clear_cart")
async def clear_cart_cb(callback: types.CallbackQuery):
    """Очистить корзину"""
    clear_cart(callback.from_user.id)
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(t(lang, "cart_cleared"), reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("remove_"))
async def remove_product(callback: types.CallbackQuery):
    """Убрать товар из корзины (уменьшить количество)"""
    product_id = int(callback.data.split("_")[1])
    
    from app.utils.cart import remove_from_cart
    remove_from_cart(callback.from_user.id, product_id, qty=1)
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
    
    await callback.answer(t(lang, "item_removed"), show_alert=False)
    
    # Перезагружаем корзину
    await show_cart(callback)