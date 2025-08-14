# app/repositories/inventory.py

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from .base import BaseRepository
from app.models import (
    Flower, Supplier, SupplyOrder, SupplyItem, InventoryBatch, 
    InventoryMovement, MovementTypeEnum, SupplyStatusEnum
)

class FlowerRepository(BaseRepository[Flower]):
    """Репозиторий для работы с цветами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Flower)
    
    async def get_active_flowers(self) -> List[Flower]:
        """Получить активные цветы"""
        result = await self.session.execute(
            select(Flower).where(Flower.is_active == True).order_by(Flower.name_ru)
        )
        return result.scalars().all()
    
    async def search_flowers(self, query: str, lang: str = "ru") -> List[Flower]:
        """Поиск цветов по названию"""
        name_field = Flower.name_ru if lang == "ru" else Flower.name_uz
        
        result = await self.session.execute(
            select(Flower).where(
                and_(
                    Flower.is_active == True,
                    name_field.ilike(f"%{query}%")
                )
            ).order_by(name_field)
        )
        return result.scalars().all()
    
    async def get_low_stock_flowers(self) -> List[Dict[str, Any]]:
        """Получить цветы с низким остатком"""
        # Подзапрос для расчета текущих остатков
        stock_subquery = (
            select(
                InventoryBatch.flower_id,
                func.sum(InventoryBatch.quantity).label('total_stock')
            )
            .group_by(InventoryBatch.flower_id)
        ).subquery()
        
        result = await self.session.execute(
            select(Flower, stock_subquery.c.total_stock)
            .join(stock_subquery, Flower.id == stock_subquery.c.flower_id)
            .where(
                and_(
                    Flower.is_active == True,
                    stock_subquery.c.total_stock <= Flower.min_stock
                )
            )
        )
        
        return [
            {
                'flower': flower,
                'current_stock': stock or 0,
                'min_stock': flower.min_stock
            }
            for flower, stock in result.all()
        ]

class SupplierRepository(BaseRepository[Supplier]):
    """Репозиторий для работы с поставщиками"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Supplier)
    
    async def get_active_suppliers(self) -> List[Supplier]:
        """Получить активных поставщиков"""
        result = await self.session.execute(
            select(Supplier).where(Supplier.is_active == True).order_by(Supplier.rating.desc())
        )
        return result.scalars().all()
    
    async def get_top_suppliers(self, limit: int = 5) -> List[Supplier]:
        """Получить топ поставщиков по рейтингу"""
        result = await self.session.execute(
            select(Supplier)
            .where(Supplier.is_active == True)
            .order_by(Supplier.rating.desc())
            .limit(limit)
        )
        return result.scalars().all()

class SupplyOrderRepository(BaseRepository[SupplyOrder]):
    """Репозиторий для работы с заказами поставщикам"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, SupplyOrder)
    
    async def get_florist_orders(self, florist_id: int, status: Optional[SupplyStatusEnum] = None) -> List[SupplyOrder]:
        """Получить заказы флориста"""
        query = select(SupplyOrder).where(SupplyOrder.florist_id == florist_id)
        
        if status:
            query = query.where(SupplyOrder.status == status)
        
        query = query.order_by(SupplyOrder.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_pending_orders(self) -> List[SupplyOrder]:
        """Получить заказы на подтверждение"""
        result = await self.session.execute(
            select(SupplyOrder)
            .where(SupplyOrder.status == SupplyStatusEnum.pending)
            .order_by(SupplyOrder.created_at.desc())
        )
        return result.scalars().all()
    
    async def create_with_items(self, order_data: Dict[str, Any], items_data: List[Dict[str, Any]]) -> SupplyOrder:
        """Создать заказ с позициями"""
        order = SupplyOrder(**order_data)
        self.session.add(order)
        await self.session.flush()
        
        total_amount = Decimal("0")
        for item_data in items_data:
            item = SupplyItem(supply_order_id=order.id, **item_data)
            self.session.add(item)
            total_amount += item_data['total_price']
        
        order.total_amount = total_amount
        await self.session.flush()
        return order

class InventoryRepository(BaseRepository[InventoryBatch]):
    """Репозиторий для работы с остатками склада"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, InventoryBatch)
    
    async def get_current_stock(self, flower_id: int) -> int:
        """Получить текущий остаток цветка"""
        result = await self.session.execute(
            select(func.sum(InventoryBatch.quantity))
            .where(InventoryBatch.flower_id == flower_id)
        )
        return result.scalar() or 0
    
    async def get_stock_by_flowers(self) -> Dict[int, int]:
        """Получить остатки всех цветов"""
        result = await self.session.execute(
            select(InventoryBatch.flower_id, func.sum(InventoryBatch.quantity))
            .group_by(InventoryBatch.flower_id)
        )
        return {flower_id: stock for flower_id, stock in result.all()}
    
    async def get_expiring_batches(self, days: int = 3) -> List[InventoryBatch]:
        """Получить партии истекающие через N дней"""
        from datetime import timedelta
        expire_date = date.today() + timedelta(days=days)
        
        result = await self.session.execute(
            select(InventoryBatch)
            .where(
                and_(
                    InventoryBatch.quantity > 0,
                    InventoryBatch.expire_date <= expire_date
                )
            )
            .order_by(InventoryBatch.expire_date)
        )
        return result.scalars().all()
    
    async def get_flower_batches(self, flower_id: int, available_only: bool = True) -> List[InventoryBatch]:
        """Получить партии цветка (FIFO)"""
        query = select(InventoryBatch).where(InventoryBatch.flower_id == flower_id)
        
        if available_only:
            query = query.where(InventoryBatch.quantity > 0)
        
        query = query.order_by(InventoryBatch.batch_date)  # FIFO
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def reserve_flowers(self, flower_id: int, quantity: int) -> List[Dict[str, Any]]:
        """Зарезервировать цветы (FIFO алгоритм)"""
        batches = await self.get_flower_batches(flower_id, available_only=True)
        
        reserved = []
        remaining = quantity
        
        for batch in batches:
            if remaining <= 0:
                break
            
            available = batch.quantity
            to_reserve = min(available, remaining)
            
            if to_reserve > 0:
                reserved.append({
                    'batch_id': batch.id,
                    'quantity': to_reserve,
                    'price': batch.purchase_price
                })
                remaining -= to_reserve
        
        if remaining > 0:
            raise ValueError(f"Недостаточно цветов на складе. Нужно: {quantity}, доступно: {quantity - remaining}")
        
        return reserved

class MovementRepository(BaseRepository[InventoryMovement]):
    """Репозиторий для работы с движениями склада"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, InventoryMovement)
    
    async def get_flower_movements(self, flower_id: int, limit: int = 50) -> List[InventoryMovement]:
        """Получить движения по цветку"""
        result = await self.session.execute(
            select(InventoryMovement)
            .where(InventoryMovement.flower_id == flower_id)
            .order_by(InventoryMovement.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_movements_by_period(self, start_date: date, end_date: date) -> List[InventoryMovement]:
        """Получить движения за период"""
        result = await self.session.execute(
            select(InventoryMovement)
            .where(
                and_(
                    func.date(InventoryMovement.created_at) >= start_date,
                    func.date(InventoryMovement.created_at) <= end_date
                )
            )
            .order_by(InventoryMovement.created_at.desc())
        )
        return result.scalars().all()
    
    async def create_movement(self, movement_data: Dict[str, Any]) -> InventoryMovement:
        """Создать движение"""
        movement = InventoryMovement(**movement_data)
        self.session.add(movement)
        await self.session.flush()
        return movement