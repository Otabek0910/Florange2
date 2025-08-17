from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import select

from app.database.database import get_session
from app.services import UserService, FloristService, ConsultationService
from app.models import RoleEnum, ConsultationStatusEnum, Consultation, ConsultationMessage
from app.translate import t
from app.exceptions import ValidationError, UserNotFoundError
import logging
from datetime import datetime


router = Router()

class ConsultationStates(StatesGroup):
    WAITING_RESPONSE = State()    # 🆕 Ожидание ответа флориста
    CHATTING = State()           # Активная консультация  
    RATING = State()             # Оценка флориста

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
    """Выбор флориста и ЗАПРОС консультации (pending статус)"""
    florist_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        consultation_service = ConsultationService(session)
        
        try:
            # 🆕 СОЗДАЕМ PENDING КОНСУЛЬТАЦИЮ (НЕ АКТИВНУЮ!)
            consultation = await consultation_service.request_consultation(user.id, florist_id)
            await session.commit()
            
            # Получаем имя флориста
            await session.refresh(consultation, ['florist'])
            florist_name = consultation.florist.first_name or "Флорист"
            
            # 🆕 НОВОЕ СООБЩЕНИЕ для клиента - ожидание ответа
            header_text = (
                f"⏳ Ожидание ответа флориста {florist_name}\n\n"
                f"💬 Можете писать сообщения - флорист получит их все сразу после принятия консультации"
            )
            
            header_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="❌ Отменить запрос", callback_data=f"cancel_consultation_{consultation.id}"),
                    types.InlineKeyboardButton(text="📞 Позвонить", callback_data=f"call_florist_{consultation.id}")
                ]
            ])
            
            # Отправляем и закрепляем header
            header_msg = await callback.message.answer(header_text, reply_markup=header_kb)
            await callback.bot.pin_chat_message(callback.message.chat.id, header_msg.message_id, disable_notification=True)
            
            # 🆕 УВЕДОМЛЯЕМ ФЛОРИСТА о ЗАПРОСЕ (НЕ об активной консультации!)
            await _notify_florist_about_consultation_request(callback.bot, consultation, session)
            
            # Переводим клиента в режим ОЖИДАНИЯ (новое состояние)
            await state.set_state(ConsultationStates.WAITING_RESPONSE)
            await state.update_data(consultation_id=consultation.id, header_message_id=header_msg.message_id)
            
            # Удаляем сообщение с выбором флориста
            await callback.message.delete()
            await callback.answer()
            
        except ValidationError as e:
            if "занят" in str(e):
                await callback.answer("Флорист занят", show_alert=True)
                await start_consultation_flow(callback, state)
            else:
                await callback.answer(str(e), show_alert=True)

@router.message(ConsultationStates.CHATTING)
async def handle_consultation_message(message: types.Message, state: FSMContext):
    """Обработка сообщений в АКТИВНОЙ консультации"""
    data = await state.get_data()
    consultation_id = data.get('consultation_id')
    
    if not consultation_id:
        await message.answer("❌ Консультация не найдена")
        await state.clear()
        return
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            # Проверяем что консультация активна
            consultation = await consultation_service.consultation_repo.get(consultation_id)
            if not consultation or consultation.status != ConsultationStatusEnum.active:
                await message.answer("❌ Консультация не активна")
                await state.clear()
                return
            
            # Сохраняем сообщение в БД
            await consultation_service.send_message(
                consultation_id, user.id, message.text, 
                message.photo[-1].file_id if message.photo else None
            )
            await session.commit()
            
            # Пересылаем другому участнику
            await session.refresh(consultation, ['client', 'florist'])
            
            if user.id == consultation.client_id:
                # Клиент написал - пересылаем флористу
                recipient = consultation.florist
                prefix = "💬 Сообщение от клиента:"
            else:
                # Флорист написал - пересылаем клиенту
                recipient = consultation.client
                prefix = "🌸 Ответ флориста:"
            
            # Отправляем сообщение
            try:
                if message.photo:
                    await message.bot.send_photo(
                        chat_id=int(recipient.tg_id),
                        photo=message.photo[-1].file_id,
                        caption=f"{prefix}\n{message.caption or message.text or ''}"
                    )
                else:
                    await message.bot.send_message(
                        chat_id=int(recipient.tg_id),
                        text=f"{prefix}\n{message.text}"
                    )
            except Exception as e:
                print(f"Error forwarding message: {e}")
                
        except Exception as e:
            print(f"Handle message error: {e}")
            await message.answer("❌ Ошибка отправки сообщения")

@router.callback_query(F.data.startswith("end_consultation_"))
async def end_consultation(callback: types.CallbackQuery, state: FSMContext):
    """Завершение консультации с полной очисткой"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        try:
            consultation_service = ConsultationService(session)
            
            # Получаем консультацию
            consultation = await consultation_service.consultation_repo.get(consultation_id)
            if not consultation:
                await callback.answer("Консультация не найдена", show_alert=True)
                return
            
            # Завершаем консультацию
            consultation.status = ConsultationStatusEnum.completed_by_client \
                if user.id == consultation.client_id \
                else ConsultationStatusEnum.completed_by_florist
            consultation.completed_at = datetime.utcnow()
            
            # Архивируем если есть сообщения
            from sqlalchemy import select
            from app.models import ConsultationMessage
            
            result = await session.execute(
                select(ConsultationMessage)
                .where(ConsultationMessage.consultation_id == consultation_id)
                .order_by(ConsultationMessage.sent_at)
            )
            messages = result.scalars().all()
            
            if messages:
                from app.services.ai_archive_service import AIArchiveService
                ai_service = AIArchiveService(callback.bot)
                
                # Генерируем тему
                theme = await ai_service.generate_consultation_theme(messages)
                consultation.theme = theme
                
                # Архивируем
                archive_id = await ai_service.archive_consultation(consultation, messages)
                consultation.archive_id = archive_id
            
            await session.commit()
            
            # Уведомляем другого участника
            other_user_id = consultation.florist_id if user.id == consultation.client_id else consultation.client_id
            await session.refresh(consultation, ['client', 'florist'])
            other_user = consultation.florist if user.id == consultation.client_id else consultation.client
            
            if other_user:
                try:
                    await callback.bot.send_message(
                        int(other_user.tg_id),
                        "Консультация завершена собеседником."
                    )
                except Exception as e:
                    print(f"Error notifying other user: {e}")
            
            # Очищаем состояние
            await state.clear()
            
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
                
        except Exception as e:
            print(f"Error ending consultation: {e}")
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
async def _notify_florist_about_consultation_request(bot, consultation, session):
    """🆕 Уведомить флориста о ЗАПРОСЕ консультации (не активной!)"""
    try:
        await session.refresh(consultation, ['client', 'florist'])
        client = consultation.client
        florist = consultation.florist
        
        text = (
            f"🌸 Запрос на консультацию!\n\n"
            f"👤 Клиент: {client.first_name}\n"
            f"📱 Запрос #{consultation.id}\n\n"
            f"💡 Примите запрос чтобы начать консультацию"
        )
        
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_consultation_{consultation.id}")],
            [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_consultation_{consultation.id}")],
            [types.InlineKeyboardButton(text="📞 Позвонить клиенту", callback_data=f"call_client_{consultation.id}")]
        ])
        
        await bot.send_message(int(florist.tg_id), text, reply_markup=kb)
        print(f"✅ Consultation request sent to florist {florist.tg_id}")
    except Exception as e:
        print(f"❌ Error notifying florist: {e}")

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


@router.callback_query(F.data.startswith("accept_consultation_"))
async def florist_accept_consultation(callback: types.CallbackQuery):
    """🆕 Флорист принимает консультацию"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user or user.role not in [RoleEnum.florist, RoleEnum.owner]:
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        
        consultation_service = ConsultationService(session)
        
        try:
            # Принимаем консультацию (меняем статус на active)
            consultation = await consultation_service.accept_consultation(consultation_id, user.id)
            
            # Получаем буферизованные сообщения и отправляем флористу
            buffered_messages = await consultation_service.flush_buffer_to_active(consultation_id)
            
            await session.commit()
            
            # Уведомляем клиента что консультация принята
            await session.refresh(consultation, ['client', 'florist'])
            client = consultation.client
            
            try:
                # 1. ПЕРВЫМ ДЕЛОМ - отправляем буферизованные сообщения флористу
                if buffered_messages:
                    await callback.bot.send_message(
                        int(user.tg_id),
                        f"📥 Сообщения от клиента {client.first_name} ({len(buffered_messages)} шт.):"
                    )
                    
                    for msg_data in buffered_messages:
                        if msg_data.get('photo_file_id'):
                            await callback.bot.send_photo(
                                int(user.tg_id),
                                photo=msg_data['photo_file_id'],
                                caption=msg_data.get('message_text', '')
                            )
                        elif msg_data.get('message_text'):
                            await callback.bot.send_message(
                                int(user.tg_id),
                                text=msg_data['message_text']
                            )
                
                # 2. Отправляем флористу меню управления консультацией
                florist_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [
                        types.InlineKeyboardButton(text="🔚 Завершить консультацию", callback_data=f"end_consultation_{consultation.id}"),
                        types.InlineKeyboardButton(text="📞 Позвонить клиенту", callback_data=f"call_client_{consultation.id}")
                    ]
                ])
                
                await callback.bot.send_message(
                    int(user.tg_id),
                    f"💬 Консультация с {client.first_name} активна!\n\nВы можете общаться в реальном времени.",
                    reply_markup=florist_kb
                )
                
                # 3. Отправляем клиенту уведомление с кнопками управления
                client_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [
                        types.InlineKeyboardButton(text="🔚 Завершить", callback_data=f"end_consultation_{consultation.id}"),
                        types.InlineKeyboardButton(text="📞 Позвонить", callback_data=f"call_florist_{consultation.id}")
                    ]
                ])
                
                await callback.bot.send_message(
                    int(client.tg_id),
                    f"✅ Флорист {user.first_name} принял консультацию!\n\n💬 Теперь вы можете общаться в реальном времени.",
                    reply_markup=client_kb
                )
                
            except Exception as e:
                print(f"Error notifying about accepted consultation: {e}")
            
            # Обновляем сообщение флориста
            await callback.message.edit_text(
                f"✅ Вы приняли консультацию с клиентом {client.first_name}!\n\nКонсультация активна.",
                reply_markup=None
            )
            await callback.answer("Консультация принята!")

            # Для флориста
            florist_key = StorageKey(
                bot_id=callback.bot.id,
                chat_id=int(user.tg_id),
                user_id=int(user.tg_id)
            )

            client_key = StorageKey(
                bot_id=callback.bot.id,
                chat_id=int(client.tg_id),
                user_id=int(client.tg_id)
            )

            storage = callback.message.bot.session.storage if hasattr(callback.message.bot, 'session') else None

            if storage:
                await storage.set_state(florist_key, ConsultationStates.CHATTING)
                await storage.set_state(client_key, ConsultationStates.CHATTING)
                await storage.set_data(florist_key, {'consultation_id': consultation.id})
                await storage.set_data(client_key, {'consultation_id': consultation.id})
                print(f"✅ Both participants set to CHATTING state")
            else:
                print("⚠️ Could not access storage, using simpler approach")

            print(f"✅ Both participants set to CHATTING state")
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
        except Exception as e:
            print(f"Accept consultation error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("decline_consultation_"))
async def florist_decline_consultation(callback: types.CallbackQuery):
    """🆕 Флорист отклоняет консультацию"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        consultation_service = ConsultationService(session)
        
        try:
            consultation = await consultation_service.consultation_repo.get(consultation_id)
            if consultation and consultation.status == ConsultationStatusEnum.pending:
                # Меняем статус на отклонено (можно добавить новый статус)
                consultation.status = ConsultationStatusEnum.force_closed
                consultation.completed_at = datetime.utcnow()
                
                await session.commit()
                
                # Уведомляем клиента
                await session.refresh(consultation, ['client'])
                client = consultation.client
                
                try:
                    await callback.bot.send_message(
                        int(client.tg_id),
                        f"❌ Флорист {user.first_name} не может принять консультацию сейчас.\n\nВыберите другого флориста."
                    )
                except:
                    pass
                
                await callback.message.edit_text(
                    "❌ Консультация отклонена.",
                    reply_markup=None
                )
                await callback.answer("Консультация отклонена")
            else:
                await callback.answer("Консультация уже недоступна", show_alert=True)
                
        except Exception as e:
            print(f"Decline consultation error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

@router.message(ConsultationStates.WAITING_RESPONSE)
async def handle_waiting_messages(message: types.Message, state: FSMContext):
    """Обработка сообщений пока флорист не ответил (буферизация)"""
    data = await state.get_data()
    consultation_id = data.get('consultation_id')
    
    if not consultation_id:
        await message.answer("❌ Консультация не найдена")
        await state.clear()
        return
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            # Добавляем сообщение в буфер
            await consultation_service.add_buffered_message(
                consultation_id, user.id, message.text, 
                message.photo[-1].file_id if message.photo else None
            )

        except Exception as e:
            print(f"Buffer message error: {e}")
            await message.answer("❌ Ошибка сохранения сообщения")


@router.callback_query(F.data.startswith("call_florist_"))
async def call_florist(callback: types.CallbackQuery):
    """Клиент просит позвонить флористу"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        # Получаем консультацию
        from sqlalchemy import select
        result = await session.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        consultation = result.scalars().first()
        
        if not consultation:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
        
        await session.refresh(consultation, ['client', 'florist'])
        
        # Отправляем запрос флористу
        client_phone = user.phone or "Не указан"
        client_name = user.first_name or "Клиент"
        
        try:
            # Кнопка для прямого звонка
            call_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"📞 Позвонить {client_phone}", url=f"tel:{client_phone}")]
            ]) if client_phone != "Не указан" else None
            
            await callback.bot.send_message(
                int(consultation.florist.tg_id),
                f"📞 Клиент {client_name} просит обратный звонок\n\n"
                f"📱 Номер: {client_phone}",
                reply_markup=call_kb
            )
            
            await callback.answer("✅ Запрос на звонок отправлен флористу")
            
        except Exception as e:
            print(f"Call request error: {e}")
            await callback.answer("❌ Ошибка отправки запроса", show_alert=True)

@router.callback_query(F.data.startswith("call_client_"))
async def call_client(callback: types.CallbackQuery):
    """Флорист просит позвонить клиенту"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        # Получаем консультацию
        from sqlalchemy import select
        result = await session.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        consultation = result.scalars().first()
        
        if not consultation:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
        
        await session.refresh(consultation, ['client', 'florist'])
        
        # Отправляем запрос клиенту
        florist_phone = user.phone or "Не указан"
        florist_name = user.first_name or "Флорист"
        
        try:
            # Кнопка для прямого звонка
            call_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"📞 Позвонить {florist_phone}", url=f"tel:{florist_phone}")]
            ]) if florist_phone != "Не указан" else None
            
            await callback.bot.send_message(
                int(consultation.client.tg_id),
                f"📞 Флорист {florist_name} хочет с вами связаться\n\n"
                f"📱 Номер: {florist_phone}",
                reply_markup=call_kb
            )
            
            await callback.answer("✅ Запрос на звонок отправлен клиенту")
            
        except Exception as e:
            print(f"Call request error: {e}")
            await callback.answer("❌ Ошибка отправки запроса", show_alert=True)