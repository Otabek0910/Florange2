from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.database.database import get_session
from app.services import FloristService, UserService
from app.models import RoleEnum
from app.translate import t
from app.exceptions import UserNotFoundError

router = Router()

class FloristProfileStates(StatesGroup):
    EDIT_BIO = State()
    EDIT_SPECIALIZATION = State()

async def _get_user_and_lang(session, tg_id: int):
    """Получить пользователя и язык"""
    user_service = UserService(session)
    try:
        user = await user_service.get_user_by_tg_id(str(tg_id))
        return user, user.lang or "ru"
    except UserNotFoundError:
        return None, "ru"

@router.callback_query(F.data == "florist_profile")
async def show_florist_profile(callback: types.CallbackQuery):
    """Показать профиль флориста"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user or user.role != RoleEnum.florist:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        florist_service = FloristService(session)
        profile = await florist_service.get_or_create_profile(user.id)
        
        # Форматируем профиль
        bio = profile.bio if profile.bio else "Не указано"
        specialization = profile.specialization if profile.specialization else "Универсальный флорист"
        rating = f"{profile.rating:.1f}" if profile.reviews_count > 0 else "нет оценок"
        
        text = (
            f"👤 <b>Мой профиль</b>\n\n"
            f"🌸 <b>Имя:</b> {user.first_name} {user.last_name or ''}\n"
            f"📝 <b>Специализация:</b> {specialization}\n"
            f"📖 <b>Описание:</b> {bio}\n"
            f"⭐ <b>Рейтинг:</b> {rating} ({profile.reviews_count} отзывов)\n"
            f"📞 <b>Телефон:</b> {user.phone or 'Не указан'}"
        )
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✏️ Изменить описание", callback_data="edit_bio")],
            [types.InlineKeyboardButton(text="🌸 Изменить специализацию", callback_data="edit_specialization")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

@router.callback_query(F.data == "edit_bio")
async def edit_bio_start(callback: types.CallbackQuery, state: FSMContext):
    """Начать редактирование описания"""
    await state.set_state(FloristProfileStates.EDIT_BIO)
    await callback.message.answer("📝 Введите новое описание для вашего профиля:")
    await callback.answer()

@router.message(FloristProfileStates.EDIT_BIO)
async def edit_bio_save(message: types.Message, state: FSMContext):
    """Сохранить новое описание"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)
        
        if not user:
            await message.answer("Ошибка: пользователь не найден")
            await state.clear()
            return
        
        florist_service = FloristService(session)
        
        try:
            # Обновляем описание
            await florist_service.update_profile(user.id, bio=message.text)
            await session.commit()
            
            await message.answer("✅ Описание обновлено!")
            await state.clear()
            
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)}")
            await state.clear()

@router.callback_query(F.data == "edit_specialization")
async def edit_specialization_start(callback: types.CallbackQuery, state: FSMContext):
    """Начать редактирование специализации"""
    await state.set_state(FloristProfileStates.EDIT_SPECIALIZATION)
    
    # Предлагаем готовые варианты
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🌹 Свадебный флорист", callback_data="spec_wedding")],
        [types.InlineKeyboardButton(text="🎂 Праздничные букеты", callback_data="spec_holiday")],
        [types.InlineKeyboardButton(text="🏢 Корпоративные композиции", callback_data="spec_corporate")],
        [types.InlineKeyboardButton(text="🌿 Интерьерная флористика", callback_data="spec_interior")],
        [types.InlineKeyboardButton(text="🌸 Универсальный флорист", callback_data="spec_universal")],
        [types.InlineKeyboardButton(text="✏️ Ввести свой вариант", callback_data="spec_custom")]
    ])
    
    await callback.message.answer("🌸 Выберите специализацию:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("spec_"))
async def save_specialization(callback: types.CallbackQuery, state: FSMContext):
    """Сохранить выбранную специализацию"""
    spec_type = callback.data.split("_")[1]
    
    specializations = {
        "wedding": "Свадебный флорист",
        "holiday": "Праздничные букеты", 
        "corporate": "Корпоративные композиции",
        "interior": "Интерьерная флористика",
        "universal": "Универсальный флорист"
    }
    
    if spec_type == "custom":
        await callback.message.answer("✏️ Введите вашу специализацию:")
        return
    
    specialization = specializations.get(spec_type, "Универсальный флорист")
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.answer("Ошибка: пользователь не найден", show_alert=True)
            await state.clear()
            return
        
        florist_service = FloristService(session)
        
        try:
            await florist_service.update_profile(user.id, specialization=specialization)
            await session.commit()
            
            await callback.message.edit_text(f"✅ Специализация изменена на: {specialization}")
            await state.clear()
            
        except Exception as e:
            await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
            await state.clear()

@router.message(FloristProfileStates.EDIT_SPECIALIZATION)
async def save_custom_specialization(message: types.Message, state: FSMContext):
    """Сохранить пользовательскую специализацию"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)
        
        if not user:
            await message.answer("Ошибка: пользователь не найден")
            await state.clear()
            return
        
        florist_service = FloristService(session)
        
        try:
            await florist_service.update_profile(user.id, specialization=message.text)
            await session.commit()
            
            await message.answer(f"✅ Специализация изменена на: {message.text}")
            await state.clear()
            
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)}")
            await state.clear()