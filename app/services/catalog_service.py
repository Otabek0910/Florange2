from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import CategoryRepository, ProductRepository
from app.models import Category, Product
from app.exceptions import ProductNotFoundError

class CatalogService:
    """Сервис для работы с каталогом"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.category_repo = CategoryRepository(session)
        self.product_repo = ProductRepository(session)
    
    async def get_categories(self) -> List[Category]:
        """Получить все категории"""
        return await self.category_repo.get_active_categories()
    
    async def get_products_by_category(self, category_id: int) -> List[Product]:
        """Получить товары категории"""
        return await self.product_repo.get_by_category(category_id, active_only=True)
    
    async def get_product(self, product_id: int) -> Product:
        """Получить товар по ID"""
        product = await self.product_repo.get(product_id)
        if not product or not product.is_active:
            raise ProductNotFoundError(product_id)
        return product
    
    async def get_popular_products(self, limit: int = 10) -> List[Product]:
        """Получить популярные товары"""
        # TODO: реализовать логику популярности
        return await self.product_repo.get_active_products(limit)
    
    async def search_products(self, query: str, lang: str = "ru") -> List[Product]:
        """Поиск товаров"""
        # TODO: реализовать поиск по названию/описанию
        raise NotImplementedError("Search not implemented yet")