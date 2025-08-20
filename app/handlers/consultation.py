from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import select, and_, delete 

from app.database.database import get_session
from app.services import UserService, FloristService, ConsultationService
from app.models import (
    RoleEnum, ConsultationStatusEnum, Consultation, 
    ConsultationMessage, ConsultationBuffer, FloristReview
)
from app.translate import t
from app.exceptions import ValidationError, UserNotFoundError
import logging
from datetime import datetime, timedelta
import os
from app.config import settings

# ✅ ИСПРАВЛЕНО: Правильный импорт архивного сервиса
try:
    from app.services.ai_archive_service import AIArchiveService
except ImportError:
    # Если сервис не готов, создаем заглушку
    class AIArchiveService:
        def __init__(self, bot):
            self.bot = bot
        async def archive_consultation_to_channel(self, consultation_id):
            return None
        async def restore_consultation_from_archive(self, chat_id, archive_id):
            return False

ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")

router = Router()

class ConsultationStates(StatesGroup):
    WAITING_RESPONSE = State()    # Ожидание ответа флориста
    CHATTING = State()           # Активная консультация 
    RATING = State()             # Оценка флориста

# ✅ ИСПРАВЛЕНО: Добавлена функция генерации ключа идемпотентности
def generate_request_key(client_id: int, florist_id: int) -> str:
    """Генерирует ключ идемпотентности для запроса консультации"""
    timestamp = int(datetime.utcnow().timestamp() // 60)  # Округляем до минут
    return f"consult_{client_id}_{florist_id}_{timestamp}"

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
                f"📍 {specialization}\n"
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
    """✅ ИСПРАВЛЕННЫЙ выбор флориста с идемпотентностью"""
    florist_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        consultation_service = ConsultationService(session)
        
        try:
            # ✅ ОЧИЩАЕМ любые старые состояния
            await state.clear()
            
            # ✅ ЗАКРЫВАЕМ любые старые консультации этого клиента
            old_consultations = await session.execute(
                select(Consultation).where(
                    and_(
                        Consultation.client_id == user.id,
                        Consultation.status.in_(['pending', 'active'])
                    )
                )
            )
            for old_consult in old_consultations.scalars():
                old_consult.status = ConsultationStatusEnum.expired
                old_consult.completed_at = datetime.utcnow()
            
            await session.commit()
            
            # ✅ СОЗДАЕМ новую консультацию с идемпотентностью
            request_key = generate_request_key(user.id, florist_id)
            consultation = await consultation_service.request_consultation_idempotent(
                user.id, florist_id, request_key
            )
            await session.commit()
            
            # ✅ УВЕДОМЛЯЕМ ФЛОРИСТА
            await session.refresh(consultation, ['florist'])
            florist_name = consultation.florist.first_name or "Флорист"
            
            try:
                await callback.bot.send_message(
                    int(consultation.florist.tg_id),
                    f"🌸 Новый запрос на консультацию!\n\n"
                    f"👤 Клиент: {user.first_name}\n"
                    f"📱 Запрос #{consultation.id}\n\n"
                    f"💡 Примите запрос чтобы начать консультацию",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_consultation_{consultation.id}")],
                        [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_consultation_{consultation.id}")],
                        [types.InlineKeyboardButton(text="📞 Номер клиента", callback_data=f"call_client_{consultation.id}")]
                    ])
                )
            except Exception as e:
                print(f"❌ Error notifying florist: {e}")
            
            # ✅ СООБЩЕНИЕ КЛИЕНТУ С ПРАВИЛЬНЫМИ КНОПКАМИ
            client_message = await callback.message.edit_text(
                f"⏳ Ожидаем ответа флориста {florist_name}\n\n"
                f"💬 Можете писать сообщения — флорист получит их после принятия консультации\n\n"
                f"🕕 Время ожидания: 15 минут",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="❌ Отменить запрос", callback_data=f"cancel_consultation_{consultation.id}")],
                    [types.InlineKeyboardButton(text="📞 Номер флориста", callback_data=f"call_florist_{consultation.id}")],
                    [types.InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
                ])
            )
            
            # ✅ ЗАКРЕПЛЯЕМ сообщение и сохраняем ID
            try:
                await callback.bot.unpin_all_chat_messages(callback.message.chat.id)
            except Exception:
                pass

            try:
                await callback.bot.pin_chat_message(callback.message.chat.id, client_message.message_id, disable_notification=True)
            except Exception:
                pass  # Игнорируем ошибки закрепления

            # ✅ ПЕРЕВОДИМ в состояние ожидания
            await state.set_state(ConsultationStates.WAITING_RESPONSE)
            await state.update_data(
                consultation_id=consultation.id, 
                header_message_id=client_message.message_id,
                florist_name=florist_name
            )
            
            await callback.answer()
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
        except Exception as e:
            print(f"Select florist error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

@router.message(ConsultationStates.CHATTING)
async def handle_consultation_message(message: types.Message, state: FSMContext):
    """✅ ИСПРАВЛЕННАЯ обработка сообщений в активной консультации"""
    data = await state.get_data()
    consultation_id = data.get('consultation_id')
    
    if not consultation_id:
        await message.answer("❌ Консультация не найдена")
        await state.clear()
        return
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)
        
        try:
            consultation = await session.get(Consultation, consultation_id)
            
            if not consultation or consultation.status != ConsultationStatusEnum.active:
                await message.answer("❌ Консультация неактивна")
                await state.clear()
                return
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # ✅ ОПРЕДЕЛЯЕМ получателя
            if user.id == consultation.client_id:
                recipient_tg_id = consultation.florist.tg_id
                sender_name = consultation.client.first_name
            elif user.id == consultation.florist_id:
                recipient_tg_id = consultation.client.tg_id
                sender_name = consultation.florist.first_name
            else:
                await message.answer("❌ Вы не участвуете в этой консультации")
                return
            
            # ✅ СОХРАНЯЕМ сообщение в БД
            consultation_msg = ConsultationMessage(
                consultation_id=consultation_id,
                sender_id=user.id,
                message_text=message.text or "",
                photo_file_id=message.photo[-1].file_id if message.photo else None
            )
            session.add(consultation_msg)
            await session.commit()
            
            # ✅ ПЕРЕСЫЛАЕМ сообщение
            try:
                if message.photo:
                    await message.bot.send_photo(
                        chat_id=int(recipient_tg_id),
                        photo=message.photo[-1].file_id,
                        caption=f"💬 {sender_name}: {message.caption or ''}"
                    )
                else:
                    await message.bot.send_message(
                        chat_id=int(recipient_tg_id),
                        text=f"💬 {sender_name}: {message.text}"
                    )
            except Exception as e:
                print(f"Error forwarding message: {e}")
                await message.answer("❌ Ошибка доставки сообщения")
                
        except Exception as e:
            print(f"Consultation message error: {e}")
            await message.answer("❌ Ошибка обработки сообщения")

@router.callback_query(F.data.startswith("end_consultation_"))
async def end_consultation(callback: types.CallbackQuery, state: FSMContext):
    """✅ ИСПРАВЛЕННОЕ завершение консультации с архивированием"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        try:
            consultation = await session.get(Consultation, consultation_id)
            if not consultation:
                await callback.answer("❌ Консультация не найдена", show_alert=True)
                return
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # Проверяем права доступа
            if user.id not in [consultation.client_id, consultation.florist_id]:
                await callback.answer("❌ Вы не участвуете в этой консультации", show_alert=True)
                return
            
            # Завершаем консультацию
            consultation.status = ConsultationStatusEnum.completed
            consultation.completed_at = datetime.utcnow()
            await session.commit()
            
            # ✅ АРХИВИРУЕМ консультацию
            try:
                ai_service = AIArchiveService(callback.bot)
                archive_id = await ai_service.archive_consultation_to_channel(consultation.id)
                
                if archive_id:
                    consultation.archive_id = archive_id
                    await session.commit()
                    print(f"✅ Consultation {consultation.id} archived with ID: {archive_id}")
                else:
                    print(f"❌ Failed to archive consultation {consultation.id}")
            except Exception as e:
                print(f"Archive error: {e}")

            # ✅ ОЧИЩАЕМ состояние
            await state.clear()
            
            # ✅ КРАСИВОЕ завершение для инициатора
            if user.id == consultation.client_id:
                await callback.message.edit_text(
                    "✅ Консультация завершена\n\n"
                    "🌸 Спасибо за обращение в Florange!\n"
                    "👍 Будем рады видеть вас снова",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                        [types.InlineKeyboardButton(text="🔍 Новая консультация", callback_data="consultation_start")]
                    ])
                )
                
                # Уведомляем флориста
                try:
                    await callback.bot.send_message(
                        int(consultation.florist.tg_id),
                        f"ℹ️ Клиент {consultation.client.first_name} завершил консультацию.\n"
                        f"✅ Консультация #{consultation_id} закрыта."
                    )
                except Exception:
                    pass
                    
            else:
                await callback.message.edit_text(
                    "✅ Консультация завершена\n\n"
                    "👍 Хорошей работы!",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ])
                )
                
                # Уведомляем клиента
                try:
                    await callback.bot.send_message(
                        int(consultation.client.tg_id),
                        f"✅ Консультация завершена\n\n"
                        f"🌸 Флорист {consultation.florist.first_name} завершил консультацию.\n"
                        f"👍 Спасибо за обращение в Florange!",
                        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                            [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                            [types.InlineKeyboardButton(text="🔍 Новая консультация", callback_data="consultation_start")]
                        ])
                    )
                except Exception:
                    pass
            
            await callback.answer("Консультация завершена")
            
        except Exception as e:
            print(f"End consultation error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

@router.message(ConsultationStates.WAITING_RESPONSE)
async def handle_waiting_messages(message: types.Message, state: FSMContext):
    """✅ ИСПРАВЛЕННАЯ обработка сообщений в ожидании"""
    data = await state.get_data()
    consultation_id = data.get('consultation_id')
    
    if not consultation_id:
        await message.answer("❌ Консультация не найдена")
        await state.clear()
        return
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, message.from_user.id)
        
        try:
            consultation = await session.get(Consultation, consultation_id)
            
            if not consultation:
                await message.answer("❌ Консультация не найдена")
                await state.clear()
                return
            
            # ✅ ПРОВЕРЯЕМ статус и переводим в активный чат если нужно
            if consultation.status == ConsultationStatusEnum.active:
                # Если пользователь еще в состоянии WAITING_RESPONSE, переводим в CHATTING
                current_state = await state.get_state()
                if current_state == ConsultationStates.WAITING_RESPONSE.state:
                    await state.set_state(ConsultationStates.CHATTING)
                    await state.update_data(consultation_id=consultation_id)
                    await handle_consultation_message(message, state)
                    return
            
            if consultation.status != ConsultationStatusEnum.pending:
                await message.answer("❌ Консультация больше неактивна")
                await state.clear()
                return
            
            # ✅ СОХРАНЯЕМ сообщение в буфер
            buffer_msg = ConsultationBuffer(
                consultation_id=consultation_id,
                sender_id=user.id,
                message_text=message.text or "",
                photo_file_id=message.photo[-1].file_id if message.photo else None
            )
            session.add(buffer_msg)
            await session.commit()
            
            # ✅ ПОДТВЕРЖДЕНИЕ сохранения
            await message.answer("📝 Сообщение сохранено. Флорист получит его после принятия консультации.")
            
        except Exception as e:
            print(f"Waiting message error: {e}")
            await message.answer("❌ Ошибка сохранения сообщения")

@router.callback_query(F.data.startswith("accept_consultation_"))
async def accept_consultation_handler(callback: types.CallbackQuery):
    """✅ ПРИНЯТИЕ консультации флористом"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            # Принимаем консультацию
            consultation = await consultation_service.accept_consultation(consultation_id, user.id)
            await session.commit()
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # ✅ ДОСТАВЛЯЕМ буферные сообщения ФЛОРИСТУ
            await _deliver_buffered_messages_to_florist(callback.bot, consultation_id, session)
            
            # Обновляем интерфейс флориста
            await callback.message.edit_text(
                f"✅ Консультация с {consultation.client.first_name} начата!\n\n"
                f"💬 Теперь вы можете общаться напрямую",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="📚 Завершить консультацию", callback_data=f"end_consultation_{consultation_id}")],
                    [types.InlineKeyboardButton(text="📞 Номер клиента", callback_data=f"call_client_{consultation_id}")]
                ])
            )
            
            # ✅ УВЕДОМЛЯЕМ клиента И ОБНОВЛЯЕМ ЕГО ИНТЕРФЕЙС
            try:
                client_chat_id = int(consultation.client.tg_id)
                
                # Отправляем новое сообщение клиенту
                new_message = await callback.bot.send_message(
                    chat_id=client_chat_id,
                    text=f"✅ Флорист {consultation.florist.first_name} принял консультацию!\n\n"
                         f"💬 Теперь можете общаться напрямую",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="📚 Завершить консультацию", callback_data=f"end_consultation_{consultation_id}")],
                        [types.InlineKeyboardButton(text="📞 Номер флориста", callback_data=f"call_florist_{consultation_id}")]
                    ])
                )
                
                # Закрепляем новое сообщение
                try:
                    await callback.bot.pin_chat_message(client_chat_id, new_message.message_id, disable_notification=True)
                except Exception:
                    pass
                
            except Exception as e:
                print(f"Error updating client interface: {e}")
            
            await callback.answer("Консультация принята!")
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
        except Exception as e:
            print(f"Accept consultation error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

async def _deliver_buffered_messages_to_florist(bot, consultation_id: int, session):
    """✅ ПРАВИЛЬНАЯ доставка буферных сообщений флористу"""
    
    # Получаем консультацию для флориста
    consultation = await session.get(Consultation, consultation_id)
    if not consultation:
        return
        
    await session.refresh(consultation, ['client', 'florist'])
    
    # Получаем буферные сообщения
    buffer_query = select(ConsultationBuffer).where(
        ConsultationBuffer.consultation_id == consultation_id
    ).order_by(ConsultationBuffer.created_at)
    
    result = await session.execute(buffer_query)
    buffered_messages = result.scalars().all()
    
    if not buffered_messages:
        return
    
    print(f"📬 Delivering {len(buffered_messages)} buffered messages to florist")
    
    # ✅ ДОСТАВЛЯЕМ каждое сообщение флористу
    try:
        for msg in buffered_messages:
            await session.refresh(msg, ['sender'])
            sender_name = msg.sender.first_name or "Клиент"
            
            if msg.photo_file_id:
                await bot.send_photo(
                    chat_id=int(consultation.florist.tg_id),
                    photo=msg.photo_file_id,
                    caption=f"📝 {sender_name} (из буфера): {msg.message_text or ''}"
                )
            else:
                await bot.send_message(
                    chat_id=int(consultation.florist.tg_id),
                    text=f"📝 {sender_name} (из буфера): {msg.message_text}"
                )
    
        # Уведомляем о количестве доставленных сообщений
        if len(buffered_messages) > 0:
            await bot.send_message(
                chat_id=int(consultation.florist.tg_id),
                text=f"📬 Доставлено {len(buffered_messages)} сообщений из буфера"
            )
    
    except Exception as e:
        print(f"Error delivering buffered messages: {e}")
    
    # Удаляем буферные сообщения
    await session.execute(
        delete(ConsultationBuffer)
        .where(ConsultationBuffer.consultation_id == consultation_id)
    )
    
    print(f"🗑️ Cleared {len(buffered_messages)} buffered messages from buffer")

@router.callback_query(F.data.startswith("decline_consultation_"))
async def decline_consultation_handler(callback: types.CallbackQuery):
    """✅ ИСПРАВЛЕННОЕ отклонение консультации флористом"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        consultation_service = ConsultationService(session)
        
        try:
            consultation = await consultation_service.decline_consultation(consultation_id, user.id)
            await session.commit()
            
            await session.refresh(consultation, ['client', 'florist'])
            
            # Обновляем сообщение флориста
            await callback.message.edit_text(
                "❌ Консультация отклонена\n\n"
                "ℹ️ Клиент будет уведомлён",
                reply_markup=None
            )
            
            # Уведомляем клиента
            try:
                await callback.bot.send_message(
                    chat_id=int(consultation.client.tg_id),
                    text=f"😔 Флорист {consultation.florist.first_name} не может принять консультацию\n\n"
                         f"🌸 Попробуйте выбрать другого флориста",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="🔍 Выбрать флориста", callback_data="consultation_start")],
                        [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ])
                )
            except Exception as e:
                print(f"Error notifying client about decline: {e}")
            
            await callback.answer("Консультация отклонена")
            
        except ValidationError as e:
            await callback.answer(str(e), show_alert=True)
        except Exception as e:
            print(f"Decline consultation error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("cancel_consultation_"))
async def cancel_consultation_request(callback: types.CallbackQuery, state: FSMContext):
    """✅ ИСПРАВЛЕННАЯ отмена консультации"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        try:
            consultation = await session.get(Consultation, consultation_id)
            
            if not consultation or consultation.client_id != user.id:
                await callback.answer("Консультация не найдена", show_alert=True)
                return
            
            # Отменяем консультацию
            consultation.status = ConsultationStatusEnum.expired
            consultation.completed_at = datetime.utcnow()
            await session.commit()
            
            # Очищаем состояние
            await state.clear()
            
            await callback.message.edit_text(
                "❌ Запрос на консультацию отменён\n\n"
                "🌸 Обращайтесь к нам в любое время!",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                    [types.InlineKeyboardButton(text="🔍 Новая консультация", callback_data="consultation_start")]
                ])
            )
            await callback.answer("Запрос отменён")
            
        except Exception as e:
            print(f"Cancel consultation error: {e}")
            await callback.answer("Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("call_florist_"))
async def call_florist(callback: types.CallbackQuery):
    """✅ ИСПРАВЛЕННЫЙ запрос номера флориста"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        consultation = await session.get(Consultation, consultation_id)
        if not consultation:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
            
        await session.refresh(consultation, ['florist'])
        florist_phone = consultation.florist.phone or "Не указан"
        
        await callback.bot.send_message(
            callback.from_user.id,
            f"📞 Номер флориста {consultation.florist.first_name}:\n\n"
            f"`{florist_phone}`\n\n"
            f"💡 Нажмите на номер чтобы скопировать",
            parse_mode="Markdown"
        )
        await callback.answer("Номер отправлен")

@router.callback_query(F.data.startswith("call_client_"))
async def call_client(callback: types.CallbackQuery):
    """✅ ИСПРАВЛЕННЫЙ запрос номера клиента"""
    consultation_id = int(callback.data.split("_")[2])
    
    async for session in get_session():
        consultation = await session.get(Consultation, consultation_id)
        if not consultation:
            await callback.answer("Консультация не найдена", show_alert=True)
            return
            
        await session.refresh(consultation, ['client'])
        client_phone = consultation.client.phone or "Не указан"
        
        await callback.bot.send_message(
            callback.from_user.id,
            f"📞 Номер клиента {consultation.client.first_name}:\n\n"
            f"`{client_phone}`\n\n"
            f"💡 Нажмите на номер чтобы скопировать",
            parse_mode="Markdown"
        )
        await callback.answer("Номер отправлен")

@router.callback_query(F.data == "consultation_history")
async def show_consultation_history(callback: types.CallbackQuery):
    """Показать историю консультаций"""
    async for session in get_session():
        user, lang = await _get_user_and_lang(session, callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Получаем завершенные консультации пользователя
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
            try:
                ai_service = AIArchiveService(callback.bot)
                success = await ai_service.restore_consultation_from_archive(
                    callback.message.chat.id, 
                    consultation.archive_id
                )
                
                if success:
                    await callback.answer("📖 Архив восстановлен")
                else:
                    await callback.message.edit_text(
                        "📝 Архив этой консультации недоступен\n"
                        "Возможно, консультация была завершена до внедрения системы архивирования."
                    )
            except Exception as e:
                print(f"Archive restore error: {e}")
                await callback.message.edit_text(
                    "📝 Ошибка восстановления архива\n"
                    "Обратитесь к администратору."
                )
        else:
            await callback.message.edit_text(
                "📝 Архив этой консультации не найден\n"
                "Возможно, консультация была завершена до внедрения системы архивирования."
            )
        
        await callback.answer()

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

async def _update_florist_rating(session, florist_id: int):
    """Обновление общего рейтинга флориста"""
    from sqlalchemy import func
    from app.models import FloristProfile
    
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