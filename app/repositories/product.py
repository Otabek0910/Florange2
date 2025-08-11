from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from app.models import Product, Category

class CategoryRepository(BaseRepository[Category]):
    """Репозиторий для работы с категориями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Category)
    
    async def get_active_categories(self) -> List[Category]:
        """Получить активные категории"""
        result = await self.session.execute(
            select(Category).order_by(Category.sort)
        )
        return result.scalars().all()

class ProductRepository(BaseRepository[Product]):
    """Репозиторий для работы с товарами"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Product)
    
    async def get_by_category(self, category_id: int, active_only: bool = True) -> List[Product]:
        """Получить товары по категории"""
        query = select(Product).where(Product.category_id == category_id)
        if active_only:
            query = query.where(Product.is_active == True)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_active_products(self, limit: int = 100) -> List[Product]:
        """Получить активные товары"""
        result = await self.session.execute(
            select(Product)
            .where(Product.is_active == True)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def update_stock(self, product_id: int, quantity: int) -> Optional[Product]:
        """Обновить количество на складе"""
        return await self.update(product_id, {"stock_qty": quantity})