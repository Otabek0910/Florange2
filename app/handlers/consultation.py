
from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.database import get_session
from app.services import UserService, FloristService, ConsultationService
from app.models import RoleEnum, ConsultationStatusEnum, Consultation, ConsultationMessage
from app.translate import t
from app.exceptions import ValidationError, UserNotFoundError
import logging
from datetime import datetime

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
    await _show_florists_page(callback, state, page=0)

@router.callback_query(F.data.startswith("florists_page_"))
async def show_florists_page(callback: types.CallbackQuery, state: FSMContext):
    """Показать страницу флористов"""
    page = int(callback.data.split("_")[2])
    await _show_florists_page(callback, state, page)

async def _show_florists_page(callback: types.CallbackQuery, state: FSMContext, page: int = 0):
    """Показать страницу с флористами"""
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
        
        # Получаем всех доступных флористов
        florist_service = FloristService(session)
        all_florists = await florist_service.get_available_florists()
        
        if not all_florists:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
            ])
            await callback.message.edit_text(t(lang, "no_florists_available"), reply_markup=kb)
            await callback.answer()
            return
        
        # Пагинация: по 3 флориста на страницу
        per_page = 3
        total_pages = (len(all_florists) + per_page - 1) // per_page
        start_idx = page * per_page
        end_idx = start_idx + per_page
        florists_on_page = all_florists[start_idx:end_idx]
        
        # Формируем кнопки флористов
        kb_rows = []
        text_lines = [f"{t(lang, 'choose_florist')} (стр. {page + 1}/{total_pages})", ""]
        
        for florist_data in florists_on_page:
            profile = florist_data['profile']
            user_obj = florist_data['user']
            status_text = florist_data['status_text']
            rating_text = florist_data['rating_text']
            is_online = florist_data['is_online']
            
            # Красивое название специализации
            specialization = profile.specialization or "Универсальный флорист"
            
            # Эмодзи статуса
            status_emoji = "🟢" if is_online else "🟡"
            
            # Кнопка: "🌸 Имя ⭐4.2 🟢"
            button_text = f"🌸 {user_obj.first_name} {rating_text} {status_emoji}"
            
            kb_rows.append([types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"select_florist_{user_obj.id}"
            )])
            
            # Детальное описание в тексте
            text_lines.append(
                f"🌸 <b>{user_obj.first_name}</b> {rating_text}\n"
                f"📝 {specialization}\n"
                f"{status_emoji} {status_text}\n"
            )
        
        # Кнопки навигации
        nav_row = []
        if page > 0:
            nav_row.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"florists_page_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(types.InlineKeyboardButton(text="Вперед ➡️", callback_data=f"florists_page_{page+1}"))
        
        if nav_row:
            kb_rows.append(nav_row)
        
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")])
        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        text = "\n".join(text_lines)
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
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
            
            # Получаем имя флориста
            await session.refresh(consultation, ['florist'])
            florist_name = consultation.florist.first_name or "Флорист"
            
            # Создаем и закрепляем управляющее сообщение
            time_str = consultation.started_at.strftime("%H:%M")
            header_text = t(lang, "consultation_header", name=florist_name, time=time_str)
            
            header_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text=t(lang, "end_consultation"), callback_data=f"end_consultation_{consultation.id}"),
                    types.InlineKeyboardButton(text=t(lang, "call_florist"), callback_data=f"call_florist_{consultation.id}")
                ]
            ])
            
            # Отправляем и закрепляем header
            header_msg = await callback.message.answer(header_text, reply_markup=header_kb)
            await callback.bot.pin_chat_message(callback.message.chat.id, header_msg.message_id, disable_notification=True)
            
            # Уведомляем флориста
            await _notify_florist_about_consultation(callback.bot, consultation, session)
            
            # Переводим клиента в режим чата
            await state.set_state(ConsultationStates.CHATTING)
            await state.update_data(consultation_id=consultation.id, header_message_id=header_msg.message_id)
            
            # Удаляем сообщение с выбором флориста
            await callback.message.delete()
            
            # Отправляем приветственное сообщение
            await callback.message.answer(t(lang, "consultation_started"))
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
    """Обработка сообщений в консультации (универсальный)"""
    data = await state.get_data()
    consultation_id = data.get('consultation_id')
    
    if not consultation_id:
        await message.answer("Консультация не найдена")
        await state.clear()
        return
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            # Получаем консультацию с участниками
            consultation = await consultation_service.get_consultation_with_participants(consultation_id)
            if not consultation:
                await message.answer("Консультация не найдена")
                await state.clear()
                return
            
            # Сохраняем сообщение
            photo_file_id = None
            if message.photo:
                photo_file_id = message.photo[-1].file_id
            
            await consultation_service.send_message(
                consultation_id, user.id, message.text, photo_file_id
            )
            await session.commit()
            
            # Определяем получателя и пересылаем
            consultation_obj = consultation['consultation']
            if user.id == consultation_obj.client_id:
                # Клиент написал - пересылаем флористу
                recipient_tg_id = consultation['florist'].tg_id
                prefix = t(lang, "consultation_message_from_client")
            else:
                # Флорист написал - пересылаем клиенту
                recipient_tg_id = consultation['client'].tg_id
                prefix = t(lang, "consultation_message_from_florist")
            
            # Пересылаем сообщение
            try:
                if message.photo:
                    await message.bot.send_photo(
                        chat_id=int(recipient_tg_id),
                        photo=message.photo[-1].file_id,
                        caption=f"{prefix}\n{message.caption or ''}"
                    )
                else:
                    await message.bot.send_message(
                        chat_id=int(recipient_tg_id),
                        text=f"{prefix}\n{message.text}"
                    )
            except Exception as e:
                print(f"Error forwarding message: {e}")
                
        except ValidationError as e:
            await message.answer(f"Ошибка: {e}")
            await state.clear()

@router.callback_query(F.data.startswith("end_consultation_"))
async def end_consultation(callback: types.CallbackQuery, state: FSMContext):
    """Завершение консультации с полной очисткой"""
    consultation_id = int(callback.data.split("_")[2])
    
    from app.database.uow import get_uow
    
    async with get_uow() as uow:
        user, lang = await _get_user_and_lang(uow.session, callback.from_user.id)
        
        try:
            # Получаем консультацию
            consultation = await uow.consultations.get(consultation_id)
            if not consultation:
                await callback.answer("Консультация не найдена", show_alert=True)
                return
            
            # Завершаем консультацию
            consultation.status = ConsultationStatusEnum.completed_by_client \
                if user.id == consultation.client_id \
                else ConsultationStatusEnum.completed_by_florist
            consultation.completed_at = datetime.utcnow()
            
            # Архивируем если есть сообщения
            messages = await uow.consultations.get_messages(consultation_id)
            if messages:
                from app.services.ai_archive_service import AIArchiveService
                ai_service = AIArchiveService(callback.bot)
                
                # Генерируем тему
                theme = await ai_service.generate_consultation_theme(messages)
                consultation.theme = theme
                
                # Архивируем
                archive_id = await ai_service.archive_consultation(consultation, messages)
                consultation.archive_id = archive_id
            
            # ВАЖНО: Очищаем состояние FSM для ОБОИХ участников
            await state.clear()
            
            # Очищаем состояние второго участника
            other_user_id = consultation.florist_id if user.id == consultation.client_id else consultation.client_id
            other_user = await uow.users.get(other_user_id)
            if other_user:
                # Создаем storage key для другого пользователя
                from aiogram.fsm.storage.base import StorageKey
                other_key = StorageKey(
                    bot_id=callback.bot.id,
                    chat_id=int(other_user.tg_id),
                    user_id=int(other_user.tg_id)
                )
                await state.storage.set_state(other_key, None)
                await state.storage.set_data(other_key, {})
            
            # Уведомляем другого участника
            if other_user:
                await callback.bot.send_message(
                    int(other_user.tg_id),
                    "Консультация завершена собеседником."
                )
            
            # Предлагаем оценить (только клиенту)
            if user.role == RoleEnum.client:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=f"⭐ {i}", callback_data=f"rate_{consultation_id}_{i}") 
                     for i in range(1, 6)],
                    [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
                ])
                await callback.message.answer(t(lang, "rate_florist_prompt"), reply_markup=kb)
            else:
                await callback.message.answer("Консультация завершена.")
            
            # Удаляем сообщения консультации
            await _clear_consultation_chat(
                callback.bot, 
                callback.message.chat.id,
                state
            )
            
        except Exception as e:
            logging.error(f"Error ending consultation: {e}")
            await callback.answer("Ошибка при завершении консультации", show_alert=True)

@router.callback_query(F.data == "consultation_history")
async def show_consultation_history(callback: types.CallbackQuery):
    """Показать историю консультаций"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Получаем завершенные консультации пользователя
        consultation_service = ConsultationService(session)
        result = await session.execute(
            select(Consultation)
            .where(
                ((Consultation.client_id == user.id) | (Consultation.florist_id == user.id)) &
                (Consultation.status != ConsultationStatusEnum.active)
            )
            .order_by(Consultation.completed_at.desc())
            .limit(10)
        )
        consultations = result.scalars().all()
        
        if not consultations:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")]
            ])
            await callback.message.edit_text(t(lang, "no_consultation_history"), reply_markup=kb)
            await callback.answer()
            return
        
        # Формируем список консультаций
        kb_rows = []
        text_lines = [t(lang, "history_consultations"), ""]
        
        for consultation in consultations:
            # Загружаем связанные данные
            await session.refresh(consultation, ['client', 'florist'])
            
            # Определяем с кем была консультация
            if consultation.client_id == user.id:
                partner_name = consultation.florist.first_name or "Флорист"
                partner_emoji = "🌸"
            else:
                partner_name = consultation.client.first_name or "Клиент"
                partner_emoji = "👤"
            
            # Форматируем дату
            date_str = consultation.started_at.strftime("%d.%m.%Y")
            theme = consultation.theme or "Консультация"
            
            # Добавляем в список
            text_lines.append(
                f"📅 {date_str} | {partner_emoji} {partner_name}\n"
                f"💬 {theme}\n"
            )
            
            # Кнопка для просмотра
            kb_rows.append([types.InlineKeyboardButton(
                text=f"{date_str} - {partner_name}: {theme[:20]}...",
                callback_data=f"view_consultation_{consultation.id}"
            )])
        
        kb_rows.append([types.InlineKeyboardButton(text=t(lang, "back_to_menu"), callback_data="main_menu")])
        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        text = "\n".join(text_lines)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

@router.callback_query(F.data.startswith("view_consultation_"))
async def view_consultation_archive(callback: types.CallbackQuery):
    """Просмотр архива консультации"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        # Получаем консультацию
        result = await session.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        consultation = result.scalars().first()
        
        if not consultation:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
        
        # Проверяем права доступа
        if consultation.client_id != user.id and consultation.florist_id != user.id:
            await callback.answer("Нет доступа к этой консультации", show_alert=True)
            return
        
        # Пока простое восстановление - в будущем из архивного канала
        if consultation.archive_id:
            from app.services.ai_archive_service import AIArchiveService
            ai_service = AIArchiveService(callback.bot)
            success = await ai_service.restore_consultation_from_archive(
                callback.message.chat.id, 
                consultation.archive_id
            )
        else:
            await callback.message.edit_text(
                "📁 Архив этой консультации не найден\n"
                "Возможно, консультация была завершена до внедрения системы архивирования."
            )
        
        await callback.answer()

@router.callback_query(F.data.startswith("call_florist_"))
async def request_call_florist(callback: types.CallbackQuery):
    """Запрос звонка флористу"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Получаем консультацию
        consultation_service = ConsultationService(session)
        consultation_data = await consultation_service.get_consultation_with_participants(consultation_id)
        
        if not consultation_data:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
        
        consultation = consultation_data['consultation']
        client = consultation_data['client']
        florist = consultation_data['florist']
        
        # Отправляем запрос флористу с номером клиента
        client_phone = client.phone or "Не указан"
        call_request_text = t(lang, "call_request_received", name=client.first_name, phone=client_phone)
        
        # Кнопка для набора номера (работает на мобильных)
        call_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"📞 Набрать {client_phone}", url=f"tel:{client_phone}")]
        ]) if client_phone != "Не указан" else None
        
        try:
            await callback.bot.send_message(
                int(florist.tg_id), 
                call_request_text, 
                reply_markup=call_kb
            )
            await callback.answer(t(lang, "call_request_sent"))
        except Exception as e:
            await callback.answer("Ошибка отправки запроса", show_alert=True)
            print(f"Error sending call request: {e}")

@router.callback_query(F.data.startswith("respond_consultation_"))
async def florist_respond_consultation(callback: types.CallbackQuery, state: FSMContext):
    """Флорист отвечает на консультацию"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        if not user or user.role not in [RoleEnum.florist, RoleEnum.owner]:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        # Проверяем что консультация активна и флорист участвует
        consultation = await consultation_service.consultation_repo.get(consultation_id)
        if not consultation or consultation.florist_id != user.id:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
        
        if consultation.status != ConsultationStatusEnum.active:
            await callback.answer("Консультация уже завершена", show_alert=True)
            return
        
        # Переводим флориста в режим чата
        await state.set_state(ConsultationStates.CHATTING)
        await state.update_data(consultation_id=consultation_id, client_id=consultation.client_id)
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔚 Завершить консультацию", callback_data=f"end_consultation_{consultation_id}")]
        ])
        
        await callback.message.edit_text(
            "💬 Вы подключены к консультации! Напишите ответ клиенту:",
            reply_markup=kb
        )
        await callback.answer()

# Обработчик сообщений флориста в консультации убираем - теперь универсальный выше

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

async def _clear_consultation_chat(bot, chat_id: int, state: FSMContext):
    """Полная очистка чата от сообщений консультации"""
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        header_message_id = data.get('header_message_id')
        
        # Сначала открепляем сообщение
        if header_message_id:
            try:
                await bot.unpin_chat_message(chat_id, header_message_id)
            except:
                pass
        
        # Удаляем последние 50 сообщений (включая закрепленное)
        latest_message = await bot.send_message(chat_id, "🧹 Очистка чата...")
        start_id = latest_message.message_id
        
        for i in range(50):  # Удаляем последние 50 сообщений
            try:
                await bot.delete_message(chat_id, start_id - i)
            except:
                continue  # Игнорируем ошибки удаления
                
    except Exception as e:
        print(f"Error clearing chat: {e}")

async def _show_main_menu_after_cleanup(bot, chat_id: int, lang: str, role: str):
    """Показать главное меню после очистки чата"""
    try:
        from app.handlers.start import _create_main_menu_keyboard
        kb = await _create_main_menu_keyboard(bot, lang, role)
        await bot.send_message(
            chat_id=chat_id,
            text=t(lang, 'menu_title'),
            reply_markup=kb
        )
    except Exception as e:
        print(f"Error showing menu after cleanup: {e}")