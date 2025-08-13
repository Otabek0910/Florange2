"""
Diana Flowers Bot v2.0
Архитектура: Clean Architecture + DDD
Стек: aiogram v3 + FastAPI + PostgreSQL + Redis
"""
__version__ = "2.0.0"

# Экспорт основных компонентов
# Ensure that database/uow.py exists and contains get_uow and UnitOfWork
from .database.uow import get_uow, UnitOfWork
from .handlers.base import BaseHandler

__all__ = ["get_uow", "UnitOfWork", "BaseHandler"]