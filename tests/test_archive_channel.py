# test_archive_channel.py - создать новый файл в корне проекта

import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot

async def test_archive_channel():
    """Тест отправки сообщения в канал архива"""
    
    # Загружаем переменные окружения
    load_dotenv()
    
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")
    
    print(f"🤖 Bot Token: {BOT_TOKEN[:20]}...")
    print(f"📁 Archive Channel ID: {ARCHIVE_CHANNEL_ID}")
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден в .env")
        return
    
    if not ARCHIVE_CHANNEL_ID:
        print("❌ ARCHIVE_CHANNEL_ID не найден в .env")
        return
    
    # Создаем бота
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Пробуем отправить тестовое сообщение
        print("📤 Отправляем тестовое сообщение...")
        
        test_message = await bot.send_message(
            chat_id=ARCHIVE_CHANNEL_ID,
            text="🧪 ТЕСТ АРХИВАЦИИ\n\n"
                 f"📅 {asyncio.get_event_loop().time()}\n"
                 "✅ Бот может отправлять сообщения в канал архива!"
        )
        
        print(f"✅ Сообщение отправлено успешно! Message ID: {test_message.message_id}")
        
        # Пробуем отправить фото
        print("📸 Тестируем отправку фото...")
        
        # Используем любое фото по URL или file_id
        photo_message = await bot.send_photo(
            chat_id=ARCHIVE_CHANNEL_ID,
            photo="https://via.placeholder.com/300x200.png?text=TEST",
            caption="🧪 Тест отправки фото в архив"
        )
        
        print(f"✅ Фото отправлено успешно! Message ID: {photo_message.message_id}")
        
        # Получаем информацию о канале
        print("📋 Получаем информацию о канале...")
        
        chat_info = await bot.get_chat(ARCHIVE_CHANNEL_ID)
        print(f"📁 Название канала: {chat_info.title}")
        print(f"👥 Тип чата: {chat_info.type}")
        print(f"📝 Описание: {chat_info.description or 'Нет описания'}")
        
        # Проверяем права бота
        print("🔐 Проверяем права бота...")
        
        bot_member = await bot.get_chat_member(ARCHIVE_CHANNEL_ID, bot.id)
        print(f"👤 Статус бота: {bot_member.status}")
        
        if hasattr(bot_member, 'can_post_messages'):
            print(f"📝 Может отправлять сообщения: {bot_member.can_post_messages}")
        if hasattr(bot_member, 'can_send_photos'):
            print(f"📸 Может отправлять фото: {bot_member.can_send_photos}")
        
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("✅ Бот может работать с каналом архива")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        print(f"❌ Тип ошибки: {type(e).__name__}")
        
        # Дополнительная диагностика
        if "chat not found" in str(e).lower():
            print("💡 Возможные причины:")
            print("   - Неправильный ID канала")
            print("   - Бот не добавлен в канал")
            print("   - Канал удален или заблокирован")
        
        elif "not enough rights" in str(e).lower():
            print("💡 Возможные причины:")
            print("   - Бот не администратор канала")
            print("   - У бота нет прав на отправку сообщений")
            print("   - Канал ограничил права ботов")
        
        elif "forbidden" in str(e).lower():
            print("💡 Возможные причины:")
            print("   - Бот заблокирован в канале")
            print("   - Канал запрещает ботам отправлять сообщения")
    
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_archive_channel())