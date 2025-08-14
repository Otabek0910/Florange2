# app/repositories/__init__.py - добавить новые репозитории

from .user import UserRepository
from .product import ProductRepository, CategoryRepository
from .order import OrderRepository
from .settings import SettingsRepository
from .florist import FloristRepository
from .consultation import ConsultationRepository
# 🆕 Новые репозитории склада
from .inventory import (
    FlowerRepository, 
    SupplierRepository, 
    SupplyOrderRepository, 
    InventoryRepository, 
    MovementRepository
)

__all__ = [
    "UserRepository",
    "ProductRepository", 
    "CategoryRepository",
    "OrderRepository",
    "SettingsRepository",
    "FloristRepository",
    "ConsultationRepository",
    # Склад
    "FlowerRepository",
    "SupplierRepository", 
    "SupplyOrderRepository",
    "InventoryRepository",
    "MovementRepository"
]