from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from app.models import Order, OrderItem, OrderStatusEnum

class OrderRepository(BaseRepository[Order]):
    """Репозиторий для работы с заказами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Order)
    
    async def get_user_orders(self, user_id: int) -> List[Order]:
        """Получить заказы пользователя"""
        result = await self.session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_orders_by_status(self, status: OrderStatusEnum) -> List[Order]:
        """Получить заказы по статусу"""
        result = await self.session.execute(
            select(Order)
            .where(Order.status == status)
            .order_by(Order.created_at.desc())
        )
        return result.scalars().all()
    
    async def create_with_items(self, order_data: dict, items_data: List[dict]) -> Order:
        """Создать заказ с позициями"""
        order = Order(**order_data)
        self.session.add(order)
        await self.session.flush()
        
        for item_data in items_data:
            item = OrderItem(order_id=order.id, **item_data)
            self.session.add(item)
        
        await self.session.flush()
        await self.session.refresh(order)
        return order
    
    async def update_status(self, order_id: int, status: OrderStatusEnum) -> Optional[Order]:
        """Обновить статус заказа"""
        return await self.update(order_id, {"status": status})