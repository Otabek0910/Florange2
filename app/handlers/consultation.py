from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.database import get_session
from app.services import UserService, FloristService, ConsultationService
from app.models import RoleEnum, ConsultationStatusEnum
from app.translate import t
from app.exceptions import ValidationError, UserNotFoundError

router = Router()

class ConsultationStates(StatesGroup):
    CHATTING = State()
    RATING = State()

async def _get_user_and_lang(session, tg_id: int):
    """Получить пользователя и язык"""
    user_service = UserService(session)
    try:
        user = await user_service.get_user_by_tg_id(str(tg_id))
        return user, user.lang or "ru"
    except UserNotFoundError:
        return None, "ru"

@router.callback_query(F.data == "consultation_start")
async def start_consultation_flow(callback: types.CallbackQuery, state: FSMContext):
    """Начать процесс выбора флориста"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user or user.role != RoleEnum.client:
            await callback.answer(t(lang, "access_denied"), show_alert=True)
            return
        
        # Проверяем нет ли активной консультации
        consultation_service = ConsultationService(session)
        active = await consultation_service.get_active_consultation(user.id)
        
        if active:
            await callback.message.edit_text(
                t(lang, "consultation_busy"),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=t(lang, "end_consultation"), callback_data=f"end_consultation_{active.id}")],
                    [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
                ])
            )
            await callback.answer()
            return
        
        # Получаем доступных флористов
        florist_service = FloristService(session)
        florists = await florist_service.get_available_florists()
        
        if not florists:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
            ])
            await callback.message.edit_text(t(lang, "no_florists_available"), reply_markup=kb)
            await callback.answer()
            return
        
        # Формируем список флористов
        kb_rows = []
        for florist_data in florists[:5]:  # Показываем первых 5
            profile = florist_data['profile']
            user_obj = florist_data['user']
            status_text = florist_data['status_text']
            rating_text = florist_data['rating_text']
            
            specialization = profile.specialization or "Флорист"
            button_text = f"{user_obj.first_name} {rating_text} ({status_text})"
            
            kb_rows.append([types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"select_florist_{user_obj.id}"
            )])
        
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")])
        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        text = f"{t(lang, 'choose_florist')}\n\n"
        for florist_data in florists[:5]:
            profile = florist_data['profile']
            user_obj = florist_data['user']
            rating_text = florist_data['rating_text']
            specialization = profile.specialization or "Флорист"
            text += f"🌸 {user_obj.first_name} {rating_text}\n📝 {specialization}\n\n"
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()

@router.callback_query(F.data.startswith("select_florist_"))
async def select_florist(callback: types.CallbackQuery, state: FSMContext):
    """Выбор флориста и начало консультации"""
    florist_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        consultation_service = ConsultationService(session)
        
        try:
            # Создаем консультацию
            consultation = await consultation_service.start_consultation(user.id, florist_id)
            await session.commit()
            
            # Уведомляем флориста
            await _notify_florist_about_consultation(callback.bot, consultation, session)
            
            # Переводим клиента в режим чата
            await state.set_state(ConsultationStates.CHATTING)
            await state.update_data(consultation_id=consultation.id, florist_id=florist_id)
            
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "end_consultation"), callback_data=f"end_consultation_{consultation.id}")]
            ])
            
            await callback.message.edit_text(t(lang, "consultation_started"), reply_markup=kb)
            await callback.answer()
            
        except ValidationError as e:
            if "занят" in str(e):
                await callback.answer(t(lang, "florist_busy"), show_alert=True)
                # Возвращаем к списку флористов
                await start_consultation_flow(callback, state)
            else:
                await callback.answer(str(e), show_alert=True)

@router.message(ConsultationStates.CHATTING)
async def handle_consultation_message(message: types.Message, state: FSMContext):
    """Обработка сообщений в консультации"""
    data = await state.get_data()
    consultation_id = data.get('consultation_id')
    florist_id = data.get('florist_id')
    
    if not consultation_id:
        await message.answer("Консультация не найдена")
        await state.clear()
        return
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            # Сохраняем сообщение
            photo_file_id = None
            if message.photo:
                photo_file_id = message.photo[-1].file_id
            
            msg_obj = await consultation_service.send_message(
                consultation_id, user.id, message.text, photo_file_id
            )
            await session.commit()
            
            # Пересылаем флористу
            await _forward_message_to_florist(message.bot, florist_id, message, lang)
            
        except ValidationError as e:
            await message.answer(f"Ошибка: {e}")
            await state.clear()

@router.callback_query(F.data.startswith("end_consultation_"))
async def end_consultation(callback: types.CallbackQuery, state: FSMContext):
    """Завершение консультации"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            consultation = await consultation_service.complete_consultation(consultation_id, user.id)
            await session.commit()
            
            if consultation:
                # Очищаем состояние
                await state.clear()
                
                # Предлагаем оценить флориста (только клиентам)
                if user.role == RoleEnum.client:
                    kb = types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text=f"⭐ 1", callback_data=f"rate_{consultation_id}_1")],
                        [types.InlineKeyboardButton(text=f"⭐ 2", callback_data=f"rate_{consultation_id}_2")],
                        [types.InlineKeyboardButton(text=f"⭐ 3", callback_data=f"rate_{consultation_id}_3")],
                        [types.InlineKeyboardButton(text=f"⭐ 4", callback_data=f"rate_{consultation_id}_4")],
                        [types.InlineKeyboardButton(text=f"⭐ 5", callback_data=f"rate_{consultation_id}_5")],
                        [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
                    ])
                    await callback.message.edit_text(t(lang, "rate_florist_prompt"), reply_markup=kb)
                else:
                    await callback.message.edit_text(t(lang, "consultation_ended"))
                
                # Уведомляем другого участника
                await _notify_consultation_ended(callback.bot, consultation, user.id, session)
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
        
        await callback.answer()

@router.callback_query(F.data.startswith("rate_"))
async def rate_florist(callback: types.CallbackQuery):
    """Оценка флориста"""
    parts = callback.data.split("_")
    consultation_id = int(parts[1])
    rating = int(parts[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            await consultation_service.rate_florist(consultation_id, user.id, rating)
            await session.commit()
            
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
            ])
            
            await callback.message.edit_text(t(lang, "rating_saved"), reply_markup=kb)
            await callback.answer()
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)

# Вспомогательные функции
async def _notify_florist_about_consultation(bot, consultation, session):
    """Уведомить флориста о новой консультации"""
    try:
        await session.refresh(consultation, ['client', 'florist'])
        client = consultation.client
        florist = consultation.florist
        
        text = (
            f"🌸 Новая консультация!\n\n"
            f"👤 Клиент: {client.first_name}\n"
            f"📱 Консультация #{consultation.id}"
        )
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💬 Ответить", callback_data=f"respond_consultation_{consultation.id}")],
            [types.InlineKeyboardButton(text="🔚 Завершить", callback_data=f"end_consultation_{consultation.id}")]
        ])
        
        await bot.send_message(int(florist.tg_id), text, reply_markup=kb)
    except Exception as e:
        print(f"Error notifying florist: {e}")

async def _forward_message_to_florist(bot, florist_id, message, lang):
    """Переслать сообщение флористу"""
    try:
        prefix = t(lang, "consultation_message_from_client")
        
        if message.photo:
            await bot.send_photo(
                chat_id=florist_id,
                photo=message.photo[-1].file_id,
                caption=f"{prefix}\n{message.caption or ''}"
            )
        else:
            await bot.send_message(
                chat_id=florist_id,
                text=f"{prefix}\n{message.text}"
            )
    except Exception as e:
        print(f"Error forwarding message: {e}")

async def _notify_consultation_ended(bot, consultation, ended_by_user_id, session):
    """Уведомить участника о завершении консультации"""
    try:
        await session.refresh(consultation, ['client', 'florist'])
        
        # Определяем кому отправлять уведомление
        if ended_by_user_id == consultation.client_id:
            target_user = consultation.florist
        else:
            target_user = consultation.client
        
        await bot.send_message(
            chat_id=int(target_user.tg_id),
            text="Консультация завершена участником."
        )
    except Exception as e:
        print(f"Error notifying about ended consultation: {e}")