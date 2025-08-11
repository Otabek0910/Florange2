from typing import List, Dict
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import OrderRepository, ProductRepository
from app.models import Order, OrderStatusEnum
from app.schemas.order import OrderCreate, OrderResponse
from app.exceptions import OrderNotFoundError, ProductNotFoundError

class OrderService:
    """Сервис для работы с заказами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.order_repo = OrderRepository(session)
        self.product_repo = ProductRepository(session)
    
    async def create_order(self, user_id: int, cart_items: Dict[int, int], 
                          order_data: OrderCreate) -> Order:
        """Создать заказ из корзины"""
        total_price = Decimal("0")
        items_data = []
        
        # Валидация товаров и расчет суммы
        for product_id, quantity in cart_items.items():
            product = await self.product_repo.get(product_id)
            if not product or not product.is_active:
                raise ProductNotFoundError(product_id)
            
            if product.stock_qty < quantity:
                raise ValueError(f"Not enough stock for product {product_id}")
            
            item_total = product.price * Decimal(str(quantity))
            total_price += item_total
            
            items_data.append({
                "product_id": product_id,
                "qty": quantity,
                "price": product.price
            })
        
        # Создание заказа
        order_dict = order_data.dict()
        order_dict.update({
            "user_id": user_id,
            "total_price": total_price,
            "status": OrderStatusEnum.new
        })
        
        order = await self.order_repo.create_with_items(order_dict, items_data)
        
        # Обновление остатков
        for product_id, quantity in cart_items.items():
            product = await self.product_repo.get(product_id)
            new_stock = product.stock_qty - quantity
            await self.product_repo.update_stock(product_id, new_stock)
        
        return order
    
    async def get_user_orders(self, user_id: int) -> List[Order]:
        """Получить заказы пользователя"""
        return await self.order_repo.get_user_orders(user_id)
    
    async def get_orders_for_florist(self) -> List[Order]:
        """Получить заказы для флориста"""
        new_orders = await self.order_repo.get_orders_by_status(OrderStatusEnum.new)
        pending_orders = await self.order_repo.get_orders_by_status(OrderStatusEnum.await_florist)
        return new_orders + pending_orders
    
    async def update_order_status(self, order_id: int, status: OrderStatusEnum) -> Order:
        """Обновить статус заказа"""
        order = await self.order_repo.update_status(order_id, status)
        if not order:
            raise OrderNotFoundError(order_id)
        return order