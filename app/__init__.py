"""
Diana Flowers Bot v2.0
Архитектура: Clean Architecture + DDD
Стек: aiogram v3 + FastAPI + PostgreSQL + Redis
"""
__version__ = "2.0.0"

# Экспорт основных компонентов
try:
    from .database.uow import get_uow, UnitOfWork
    from .handlers.base import BaseHandler
    __all__ = ["get_uow", "UnitOfWork", "BaseHandler"]
except ImportError:
    # Если модули не найдены, пропускаем
    __all__ = []