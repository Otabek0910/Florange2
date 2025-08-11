from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel
from app.models import OrderStatusEnum

class OrderItemResponse(BaseModel):
    """Позиция заказа"""
    product_id: int
    qty: int
    price: Decimal
    
    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    """Базовая схема заказа"""
    user_id: int
    address: Optional[str] = None
    phone: Optional[str] = None
    comment: Optional[str] = None

class OrderCreate(OrderBase):
    """Создание заказа"""
    slot_at: Optional[datetime] = None

class OrderResponse(OrderBase):
    """Ответ с данными заказа"""
    id: int
    total_price: Decimal
    status: OrderStatusEnum
    created_at: datetime
    items: List[OrderItemResponse] = []
    
    class Config:
        from_attributes = True