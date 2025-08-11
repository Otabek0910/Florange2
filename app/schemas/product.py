from typing import Optional
from decimal import Decimal
from pydantic import BaseModel

class ProductBase(BaseModel):
    """Базовая схема товара"""
    name_ru: str
    name_uz: str
    desc_ru: Optional[str] = None
    desc_uz: Optional[str] = None
    price: Decimal
    category_id: int

class ProductCreate(ProductBase):
    """Создание товара"""
    stock_qty: int = 0
    is_active: bool = True

class ProductResponse(ProductBase):
    """Ответ с данными товара"""
    id: int
    stock_qty: int
    is_active: bool
    photo_url: Optional[str] = None
    
    class Config:
        from_attributes = True