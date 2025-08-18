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

from aiogram.fsm.storage.base import StorageKey
import os
from app.services.consultation_service import generate_request_key
from app.config import settings

ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")

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
                await message.answer("❌ Консультация неактивна")
                await state.clear()
                return
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # Определяем кому переслать сообщение
            if user.id == consultation.client_id:
                # Сообщение от КЛИЕНТА → пересылаем ФЛОРИСТУ
                recipient_tg_id = consultation.florist.tg_id
                sender_name = consultation.client.first_name or "Клиент"
                sender_role = "👤 Клиент"
            elif user.id == consultation.florist_id:
                # Сообщение от ФЛОРИСТА → пересылаем КЛИЕНТУ  
                recipient_tg_id = consultation.client.tg_id
                sender_name = consultation.florist.first_name or "Флорист"
                sender_role = "🌸 Флорист"
            else:
                await message.answer("❌ Вы не участвуете в этой консультации")
                return
            
            # ✅ ОСНОВНОЕ ИСПРАВЛЕНИЕ: Пересылаем сообщение получателю
            try:
                # Формируем текст с указанием отправителя
                forwarded_text = f"{sender_role} {sender_name}:\n{message.text}"
                
                # Пересылаем получателю
                if message.photo:
                    await message.copy_to(
                        chat_id=int(recipient_tg_id),
                        caption=f"{sender_role} {sender_name}"
                    )
                else:
                    await message.copy_to(
                        chat_id=int(recipient_tg_id),
                        reply_markup=None
                    )
                    # Добавляем подпись отправителя отдельным сообщением
                    await message.bot.send_message(
                        chat_id=int(recipient_tg_id),
                        text=f"↑ {sender_role} {sender_name}"
                    )
                
                # Подтверждаем отправителю
                await message.react([types.ReactionTypeEmoji(emoji="✅")])
                
            except Exception as e:
                print(f"Error forwarding message: {e}")
                await message.answer("❌ Ошибка доставки сообщения")
                
        except Exception as e:
            print(f"Consultation message error: {e}")
            await message.answer("❌ Ошибка обработки сообщения")

@router.callback_query(F.data.startswith("end_consultation_"))
async def end_consultation(callback: types.CallbackQuery, state: FSMContext):
    """✅ ИСПРАВЛЕННОЕ завершение консультации"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            consultation = await consultation_service.consultation_repo.get(consultation_id)
            if not consultation:
                await callback.answer("❌ Консультация не найдена", show_alert=True)
                return
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # Проверяем права доступа
            if user.id not in [consultation.client_id, consultation.florist_id]:
                await callback.answer("❌ Вы не участвуете в этой консультации", show_alert=True)
                return
            
            if consultation.status != ConsultationStatusEnum.active:
                await callback.answer("❌ Консультация уже завершена", show_alert=True)
                return
            
            # ✅ ИСПРАВЛЕНИЕ: Завершаем консультацию корректно
            await consultation_service.complete_consultation(consultation_id, user.id)
            await session.commit()
            
            # Определяем кто завершил и кому уведомить
            if user.id == consultation.client_id:
                # ✅ КЛИЕНТ завершил - предлагаем оценить флориста
                await callback.message.edit_text(
                    f"✅ Консультация завершена!\n\n"
                    f"🌟 Оцените работу флориста {consultation.florist.first_name}:",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [
                            types.InlineKeyboardButton(text="⭐", callback_data=f"rate_florist_{consultation_id}_1"),
                            types.InlineKeyboardButton(text="⭐⭐", callback_data=f"rate_florist_{consultation_id}_2"),
                            types.InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"rate_florist_{consultation_id}_3")
                        ],
                        [
                            types.InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"rate_florist_{consultation_id}_4"),
                            types.InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"rate_florist_{consultation_id}_5")
                        ],
                        [types.InlineKeyboardButton(text="🚫 Пропустить", callback_data=f"skip_rating_{consultation_id}")]
                    ])
                )
                
                # Переводим клиента в состояние оценки
                await state.set_state(ConsultationStates.RATING)
                await state.update_data(consultation_id=consultation_id)
                
                other_user = consultation.florist
                other_role = "флористу"
                ender_name = consultation.client.first_name or "Клиент"
                
            else:
                # ФЛОРИСТ завершил - обычное завершение
                ender_name = consultation.florist.first_name or "Флорист"
                other_user = consultation.client
                other_role = "клиенту"
                
                await callback.message.edit_text(
                    f"✅ Консультация завершена.\n"
                    f"Спасибо за работу! 🌸",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
                    ])
                )
            
            # ✅ ИСПРАВЛЕНИЕ: Уведомляем ДРУГОГО участника (не удаляем у него сообщения)
            try:
                await callback.bot.send_message(
                    chat_id=int(other_user.tg_id),
                    text=f"✅ Консультация завершена {other_role} {ender_name}.\n"
                         f"Спасибо за использование нашего сервиса! 🌸",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
                    ])
                )
                
                # ✅ ИСПРАВЛЕНИЕ: Очищаем состояния FSM у ОБОИХ участников
                from aiogram.fsm.storage.base import StorageKey
                
                # Очищаем состояние инициатора
                initiator_key = StorageKey(
                    bot_id=callback.bot.id, 
                    chat_id=int(user.tg_id), 
                    user_id=int(user.tg_id)
                )
                
                # Очищаем состояние другого участника
                other_key = StorageKey(
                    bot_id=callback.bot.id, 
                    chat_id=int(other_user.tg_id), 
                    user_id=int(other_user.tg_id)
                )
                
                # Получаем storage из callback
                if hasattr(callback.bot, 'session') and hasattr(callback.bot.session, 'storage'):
                    storage = callback.bot.session.storage
                elif hasattr(callback, 'bot') and hasattr(callback.bot, '_session') and hasattr(callback.bot._session, 'storage'):
                    storage = callback.bot._session.storage
                else:
                    # Fallback - очищаем через state
                    await state.clear()
                    print("⚠️ Storage not accessible, cleared local state only")
                    
                if 'storage' in locals():
                    try:
                        await storage.set_state(initiator_key, None)
                        await storage.set_state(other_key, None)
                        print(f"✅ Cleared FSM states for both participants")
                    except Exception as e:
                        print(f"Storage clear error: {e}")
                        await state.clear()  # Fallback
                        
            except Exception as e:
                print(f"Error notifying other participant: {e}")
            
            await callback.answer("✅ Консультация завершена")
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
        except Exception as e:
            print(f"End consultation error: {e}")
            await callback.answer("❌ Ошибка завершения консультации", show_alert=True)

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
        clean_phone = client_phone.replace("+", "") if client_phone != "Не указан" else ""
        call_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"📞 Набрать {client_phone}", url=f"tel:{clean_phone}")]
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

@router.callback_query(F.data.startswith("rate_florist_"))
async def rate_florist(callback: types.CallbackQuery, state: FSMContext):
    """Обработка оценки флориста клиентом"""
    parts = callback.data.split("_")
    consultation_id = int(parts[2])
    rating = int(parts[3])  # 1-5 звёзд
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        try:
            # Получаем консультацию с флористом
            consultation = await session.get(Consultation, consultation_id)
            if not consultation:
                await callback.answer("❌ Консультация не найдена", show_alert=True)
                return
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # Проверяем что это клиент консультации
            if user.id != consultation.client_id:
                await callback.answer("❌ Только клиент может оценить флориста", show_alert=True)
                return
            
            # Проверяем нет ли уже оценки
            from app.models import FloristReview
            existing_review = await session.execute(
                select(FloristReview).where(FloristReview.consultation_id == consultation_id)
            )
            
            if existing_review.scalar_one_or_none():
                await callback.answer("❌ Оценка уже оставлена", show_alert=True)
                return
            
            # Создаём оценку
            review = FloristReview(
                consultation_id=consultation_id,
                client_id=user.id,
                florist_id=consultation.florist_id,
                rating=rating,
                created_at=datetime.utcnow()
            )
            session.add(review)
            
            # Обновляем общий рейтинг флориста
            await _update_florist_rating(session, consultation.florist_id)
            
            await session.commit()
            
            # Показываем благодарность
            stars = "⭐" * rating
            await callback.message.edit_text(
                f"🌟 Спасибо за оценку!\n\n"
                f"Ваша оценка флориста {consultation.florist.first_name}: {stars}\n\n"
                f"Ваш отзыв поможет нам улучшить сервис! 🌸",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
                ])
            )
            
            # Уведомляем флориста о полученной оценке
            try:
                await callback.bot.send_message(
                    chat_id=int(consultation.florist.tg_id),
                    text=f"🌟 Вы получили оценку от клиента {consultation.client.first_name}!\n\n"
                         f"Оценка: {stars}\n"
                         f"Спасибо за качественную работу! 🌸"
                )
            except Exception as e:
                print(f"Error notifying florist about rating: {e}")
            
            # Очищаем состояние
            await state.clear()
            await callback.answer(f"✅ Оценка {stars} сохранена!")
            
        except Exception as e:
            print(f"Rating error: {e}")
            await callback.answer("❌ Ошибка сохранения оценки", show_alert=True)

@router.callback_query(F.data.startswith("skip_rating_"))
async def skip_rating(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск оценки флориста"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        try:
            consultation = await session.get(Consultation, consultation_id)
            if consultation:
                await session.refresh(consultation, ['florist'])
                
                await callback.message.edit_text(
                    f"✅ Консультация завершена.\n"
                    f"Спасибо за использование нашего сервиса! 🌸\n\n"
                    f"Если захотите оценить флориста {consultation.florist.first_name} позже, "
                    f"обратитесь к администратору.",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
                    ])
                )
            
            await state.clear()
            await callback.answer("Оценка пропущена")
            
        except Exception as e:
            print(f"Skip rating error: {e}")
            await callback.answer("❌ Ошибка", show_alert=True)


async def _update_florist_rating(session, florist_id: int):
    """Обновление общего рейтинга флориста"""
    from app.models import FloristReview, FloristProfile
    from sqlalchemy import func
    
    # Вычисляем средний рейтинг и количество отзывов
    result = await session.execute(
        select(
            func.avg(FloristReview.rating).label('avg_rating'),
            func.count(FloristReview.id).label('reviews_count')
        ).where(FloristReview.florist_id == florist_id)
    )
    
    stats = result.first()
    avg_rating = float(stats.avg_rating) if stats.avg_rating else 0.0
    reviews_count = stats.reviews_count if stats.reviews_count else 0
    
    # Обновляем профиль флориста
    florist_profile = await session.execute(
        select(FloristProfile).where(FloristProfile.user_id == florist_id)
    )
    profile = florist_profile.scalar_one_or_none()
    
    if profile:
        profile.rating = round(avg_rating, 2)
        profile.reviews_count = reviews_count
        profile.updated_at = datetime.utcnow()
    
    print(f"Updated florist {florist_id} rating: {avg_rating:.2f} ({reviews_count} reviews)")


# 🆕 ДОБАВЬТЕ обработчик для состояния RATING (если клиент пишет текст вместо кнопок)
@router.message(ConsultationStates.RATING)
async def handle_rating_state_message(message: types.Message, state: FSMContext):
    """Обработка сообщений в состоянии оценки"""
    data = await state.get_data()
    consultation_id = data.get('consultation_id')
    
    if consultation_id:
        await message.answer(
            "🌟 Пожалуйста, используйте кнопки выше для оценки флориста.\n"
            "Выберите количество звёзд от 1 до 5:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="⭐", callback_data=f"rate_florist_{consultation_id}_1"),
                    types.InlineKeyboardButton(text="⭐⭐", callback_data=f"rate_florist_{consultation_id}_2"),
                    types.InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"rate_florist_{consultation_id}_3")
                ],
                [
                    types.InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"rate_florist_{consultation_id}_4"),
                    types.InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"rate_florist_{consultation_id}_5")
                ],
                [types.InlineKeyboardButton(text="🚫 Пропустить", callback_data=f"skip_rating_{consultation_id}")]
            ])
        )
    else:
        await state.clear()
        await message.answer("❌ Ошибка состояния. Начните заново.")


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

@router.callback_query(F.data.startswith("accept_consultation_"))
async def accept_consultation_handler(callback: types.CallbackQuery):
    """🆕 Принятие консультации с доставкой буферных сообщений"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            # 🆕 Принимаем консультацию (с проверками и доставкой буфера)
            consultation = await consultation_service.accept_consultation(consultation_id, user.id)
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # Уведомляем клиента о принятии
            try:
                await callback.bot.send_message(
                    chat_id=int(consultation.client.tg_id),
                    text=f"✅ Флорист {consultation.florist.first_name} принял вашу консультацию!\n"
                         f"Теперь вы можете общаться напрямую.\n\n"
                         f"Для завершения консультации используйте /end_consultation",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="📞 Позвонить флористу", callback_data=f"call_florist_{consultation.id}")],
                        [types.InlineKeyboardButton(text="❌ Завершить консультацию", callback_data=f"end_consultation_{consultation.id}")]
                    ])
                )
                
                # 🆕 Переводим клиента в состояние CHATTING
                from aiogram.fsm.storage.base import StorageKey
                storage_key = StorageKey(bot_id=callback.bot.id, chat_id=int(consultation.client.tg_id), user_id=int(consultation.client.tg_id))
                await callback.bot.fsm.storage.set_state(key=storage_key, state=ConsultationStates.CHATTING)
                await callback.bot.fsm.storage.update_data(key=storage_key, data={'consultation_id': consultation.id})
                
            except Exception as e:
                print(f"Error notifying client: {e}")
            
            # Обновляем сообщение флориста
            await callback.message.edit_text(
                f"✅ Консультация принята!\n"
                f"Клиент: {consultation.client.first_name}\n"
                f"Теперь вы можете общаться напрямую.",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="❌ Завершить консультацию", callback_data=f"end_consultation_{consultation.id}")]
                ])
            )
            
            await callback.answer("Консультация принята!")
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
            
            # Обновляем сообщение при ошибке
            if "истекла" in str(e):
                await callback.message.edit_text(
                    "❌ Консультация истекла (прошло более 15 минут)",
                    reply_markup=None
                )
            else:
                await callback.message.edit_text(
                    f"❌ Ошибка: {str(e)}",
                    reply_markup=None
                )
        
        except Exception as e:
            print(f"Accept consultation error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("decline_consultation_"))
async def decline_consultation_handler(callback: types.CallbackQuery):
    """🆕 Отклонение консультации с очисткой буфера"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            # 🆕 Отклоняем консультацию (с очисткой буфера)
            consultation = await consultation_service.decline_consultation(consultation_id, user.id)
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # Уведомляем клиента об отклонении
            try:
                await callback.bot.send_message(
                    chat_id=int(consultation.client.tg_id),
                    text=f"😔 Флорист {consultation.florist.first_name} не может принять консультацию.\n"
                         f"Попробуйте выбрать другого флориста.",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🌸 Выбрать другого флориста", callback_data="consultation_start")],
                        [types.InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
                    ])
                )
                
                # 🆕 Очищаем состояние клиента
                from aiogram.fsm.storage.base import StorageKey
                storage_key = StorageKey(bot_id=callback.bot.id, chat_id=int(consultation.client.tg_id), user_id=int(consultation.client.tg_id))
                await callback.bot.fsm.storage.set_state(key=storage_key, state=None)
                
            except Exception as e:
                print(f"Error notifying client about decline: {e}")
            
            # Обновляем сообщение флориста
            await callback.message.edit_text(
                "❌ Консультация отклонена.",
                reply_markup=None
            )
            
            await callback.answer("Консультация отклонена")
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
        except Exception as e:
            print(f"Decline consultation error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

@router.message(ConsultationStates.WAITING_RESPONSE)
async def handle_waiting_messages_improved(message: types.Message, state: FSMContext):
    """🆕 Улучшенная обработка сообщений в режиме ожидания"""
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
            # Проверяем статус консультации
            consultation = await session.get(Consultation, consultation_id)
            
            if not consultation:
                await message.answer("❌ Консультация не найдена")
                await state.clear()
                return
            
            if consultation.status == ConsultationStatusEnum.active:
                # Консультация уже активна - переводим в режим чата
                await state.set_state(ConsultationStates.CHATTING)
                await handle_consultation_message(message, state)
                return
            
            if consultation.status != ConsultationStatusEnum.pending:
                await message.answer("❌ Консультация больше неактивна")
                await state.clear()
                return
            
            # Проверяем таймаут
            if consultation.expires_at and consultation.expires_at < datetime.utcnow():
                consultation.status = ConsultationStatusEnum.expired
                await session.commit()
                await message.answer(
                    "⏰ Время ожидания истекло (15 минут).\n"
                    "Попробуйте выбрать другого флориста.",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🌸 Выбрать флориста", callback_data="consultation_start")]
                    ])
                )
                await state.clear()
                return
            
            # 🆕 Добавляем сообщение в буфер с улучшенной обработкой
            await consultation_service.add_buffered_message(
                consultation_id, 
                user.id, 
                message.text,
                message.photo[-1].file_id if message.photo else None
            )
            
            # ✅ ИСПРАВЛЕНИЕ: Убираем проблемную реакцию, оставляем простое подтверждение
            # await message.react([types.ReactionTypeEmoji(emoji="💌")])  # ❌ УБРАЛИ
            
            # Периодически напоминаем о статусе
            import random
            if random.randint(1, 3) == 1:  # 33% вероятность
                remaining_minutes = max(0, int((consultation.expires_at - datetime.utcnow()).total_seconds() / 60))
                await message.answer(
                    f"💌 Сообщение сохранено. Флорист получит его после принятия консультации.\n"
                    f"⏱ Осталось времени: {remaining_minutes} мин.",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="❌ Отменить запрос", callback_data=f"cancel_request_{consultation_id}")]
                    ])
                )
            else:
                # Простое подтверждение без кнопок
                await message.answer("💌 Сохранено")

        except Exception as e:
            print(f"Buffer message error: {e}")
            await message.answer("❌ Ошибка сохранения сообщения")

@router.callback_query(F.data.startswith("call_florist_"))  
async def call_florist(callback: types.CallbackQuery):
    """Клиент запрашивает номер флориста"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        consultation = await session.get(Consultation, consultation_id)
        if not consultation:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
            
        await session.refresh(consultation, ['florist'])
        florist_phone = consultation.florist.phone or "Не указан"
        
        # Отправляем номер текстом
        await callback.message.answer(
            f"📞 Номер флориста: `{florist_phone}`\n\n"
            f"Нажмите на номер чтобы скопировать и позвоните через приложение телефона.",
            parse_mode="Markdown"
        )
        await callback.answer("Номер отправлен")

        if florist_phone != "Не указан":
            clean_phone = florist_phone.replace("+", "")
            tel_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"📞 Набрать", url=f"tel:{clean_phone}")]
            ])
            await callback.message.answer("👆 Или нажмите кнопку:", reply_markup=tel_kb)

### 1.2 call_client() - флорист просит позвонить клиенту  
@router.callback_query(F.data.startswith("call_client_"))
async def call_client(callback: types.CallbackQuery):
    """Флорист запрашивает номер клиента"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        consultation = await session.get(Consultation, consultation_id)
        if not consultation:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
            
        await session.refresh(consultation, ['client'])
        client_phone = consultation.client.phone or "Не указан"
        
        # Отправляем номер текстом с инструкцией
        await callback.message.answer(
            f"📞 Номер клиента: `{client_phone}`\n\n"
            f"Нажмите на номер чтобы скопировать и позвоните через приложение телефона.",
            parse_mode="Markdown"
        )
        await callback.answer("Номер отправлен")

        if client_phone != "Не указан":
            clean_phone = client_phone.replace("+", "")
            tel_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"📞 Набрать", url=f"tel:{clean_phone}")]
            ])
            await callback.message.answer("👆 Или нажмите кнопку:", reply_markup=tel_kb)

### 1.3 show_phone_info() - новый обработчик для кнопки "Номер"
@router.callback_query(F.data == "show_phone")
async def show_phone_info(callback: types.CallbackQuery):
    """Показать информацию о номере телефона"""
    await callback.answer("💡 Скопируйте номер телефона и наберите его через стандартное приложение", show_alert=True)

## ШАГ 2: Добавление обработчика отмены запроса клиентом

@router.callback_query(F.data.startswith("cancel_request_"))
async def cancel_consultation_request(callback: types.CallbackQuery, state: FSMContext):
    """🆕 Отмена запроса консультации клиентом"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            # Отменяем консультацию (используем decline от имени клиента)
            consultation = await consultation_service.decline_consultation(consultation_id, user.id)
            
            await callback.message.edit_text(
                "❌ Запрос на консультацию отменён.",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🌸 Выбрать другого флориста", callback_data="consultation_start")],
                    [types.InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
                ])
            )
            
            await state.clear()
            await callback.answer("Запрос отменён")
            
        except Exception as e:
            print(f"Cancel request error: {e}")
            await callback.answer("Ошибка отмены", show_alert=True)


