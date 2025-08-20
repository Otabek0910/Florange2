# main.py - решение через SelectorEventLoop
import sys
import asyncio
import logging

# РЕШЕНИЕ: Используем SelectorEventLoop вместо ProactorEventLoop
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.handlers import start, catalog, cart, checkout, admin, orders, consultation, florist
from app.middleware.auth import AuthMiddleware
from app.middleware.state_validation import StateValidationMiddleware, ConsultationCleanupMiddleware
from app.database.database import init_db, close_db, get_engine

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

async def cleanup_resources(bot=None, dp=None):
    """Полная очистка всех ресурсов"""
    print("🧹 Закрываем ресурсы...")
    
    # 1. Закрываем Dispatcher storage
    if dp and hasattr(dp, 'storage'):
        try:
            if hasattr(dp.storage, 'close'):
                await dp.storage.close()
            if hasattr(dp.storage, 'wait_closed'):
                await dp.storage.wait_closed()
            print("✅ Dispatcher storage закрыт")
        except Exception as e:
            print(f"Storage close error: {e}")
    
    # 2. Закрываем Bot session (aiohttp)
    if bot:
        try:
            if hasattr(bot, '_session') and bot._session:
                await bot._session.close()
            elif hasattr(bot, 'session') and bot.session:
                await bot.session.close()
            print("✅ Bot session закрыта")
        except Exception as e:
            print(f"Bot session close error: {e}")
    
    # 3. Закрываем SQLAlchemy engine
    try:
        engine = get_engine()
        if engine:
            await engine.dispose()
            print("✅ SQLAlchemy engine закрыт")
    except Exception as e:
        print(f"Engine dispose error: {e}")
    
    # 4. Закрываем Redis
    try:
        from app.utils.cart import cart_manager
        await cart_manager.close()
    except Exception as e:
        print(f"Redis close error: {e}")
    
    # 5. Общее закрытие БД
    try:
        await close_db()
    except Exception as e:
        print(f"DB close error: {e}")
    
    print("✅ Все ресурсы закрыты")

async def main():
    """Главная функция приложения"""
    bot = None
    dp = None
    
    try:
        config.validate()
        await init_db()
        
        if "--seed" in sys.argv:
            from app.utils.seed import load_seed_data
            await load_seed_data()
            return

        storage = MemoryStorage()
        bot = Bot(token=config.BOT_TOKEN)
        dp = Dispatcher(storage=storage)

        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        dp.message.middleware(StateValidationMiddleware())
        dp.callback_query.middleware(StateValidationMiddleware())
        dp.message.middleware(ConsultationCleanupMiddleware(cleanup_frequency=100))
        print("✅ Middleware зарегистрированы")

        dp.include_router(start.router)
        dp.include_router(catalog.router)
        dp.include_router(cart.router)
        dp.include_router(checkout.router)
        dp.include_router(admin.router)
        dp.include_router(orders.router)
        dp.include_router(consultation.router)
        dp.include_router(florist.router)
        
        print("🌸 Florange Bot запущен...")
        
        await dp.start_polling(bot)
        
    except KeyboardInterrupt:
        print("\n🛑 Завершение...")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await cleanup_resources(bot, dp)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()