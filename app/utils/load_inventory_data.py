# app/utils/load_inventory_simple.py

import asyncio
from datetime import datetime, timedelta
from app.database.database import get_session
from app.models import (
    Flower, Supplier, InventoryBatch, InventoryMovement, 
    MovementTypeEnum, User, RoleEnum
)

async def load_inventory_simple():
    """Загрузить тестовые данные склада (упрощенная версия)"""
    
    async for session in get_session():
        try:
            print("🔍 Поиск администратора...")
            
            # Найти существующего админа
            from sqlalchemy import select
            result = await session.execute(select(User).where(User.role == RoleEnum.owner))
            admin_user = result.scalars().first()
            
            if not admin_user:
                print("❌ Администратор не найден. Создайте сначала: python -m app.utils.create_admin YOUR_TG_ID")
                return
            
            print(f"✅ Найден администратор: {admin_user.first_name} (ID: {admin_user.id})")
            
            # 1. Цветы
            print("🌸 Создание цветов...")
            flowers_data = [
                {'name_ru': 'Роза красная', 'name_uz': 'Qizil atirgul', 'unit_type': 'piece', 'min_stock': 50, 'max_stock': 200, 'shelf_life_days': 7},
                {'name_ru': 'Роза белая', 'name_uz': 'Oq atirgul', 'unit_type': 'piece', 'min_stock': 30, 'max_stock': 150, 'shelf_life_days': 7},
                {'name_ru': 'Тюльпан красный', 'name_uz': 'Qizil lola', 'unit_type': 'piece', 'min_stock': 100, 'max_stock': 300, 'shelf_life_days': 5},
                {'name_ru': 'Гипсофила', 'name_uz': 'Gipsofila', 'unit_type': 'bundle', 'min_stock': 10, 'max_stock': 50, 'shelf_life_days': 14},
                {'name_ru': 'Упаковочная бумага', 'name_uz': 'Orash qogozi', 'unit_type': 'sheet', 'min_stock': 50, 'max_stock': 200, 'shelf_life_days': 365},
            ]
            
            flowers = []
            for data in flowers_data:
                flower = Flower(**data)
                session.add(flower)
                flowers.append(flower)
            
            await session.flush()
            print(f"✅ Создано {len(flowers)} цветов")
            
            # 2. Поставщики
            print("🏪 Создание поставщиков...")
            suppliers_data = [
                {'name': 'ЦветТорг', 'contact_person': 'Александр Иванов', 'phone': '+998901234567', 'rating': 4.5},
                {'name': 'Узбек Гуль', 'contact_person': 'Дилшод Каримов', 'phone': '+998901234569', 'rating': 4.8},
            ]
            
            suppliers = []
            for data in suppliers_data:
                supplier = Supplier(**data)
                session.add(supplier)
                suppliers.append(supplier)
            
            await session.flush()
            print(f"✅ Создано {len(suppliers)} поставщиков")
            
            # 3. Начальные партии (без движений пока)
            print("📦 Создание партий...")
            today = datetime.now().date()
            batches_data = [
                # Партии от первого поставщика
                {'flower': flowers[0], 'supplier': suppliers[0], 'quantity': 150, 'purchase_price': 2500, 'expire_date': today + timedelta(days=7)},
                {'flower': flowers[1], 'supplier': suppliers[0], 'quantity': 100, 'purchase_price': 2300, 'expire_date': today + timedelta(days=7)},
                {'flower': flowers[2], 'supplier': suppliers[0], 'quantity': 200, 'purchase_price': 1500, 'expire_date': today + timedelta(days=5)},
                # Партии от второго поставщика
                {'flower': flowers[3], 'supplier': suppliers[1], 'quantity': 40, 'purchase_price': 3000, 'expire_date': today + timedelta(days=14)},
                {'flower': flowers[4], 'supplier': suppliers[1], 'quantity': 150, 'purchase_price': 300, 'expire_date': today + timedelta(days=365)},
            ]
            
            batches = []
            for data in batches_data:
                batch = InventoryBatch(
                    flower_id=data['flower'].id,
                    supplier_id=data['supplier'].id,
                    quantity=data['quantity'],
                    purchase_price=data['purchase_price'],
                    batch_date=today,
                    expire_date=data['expire_date']
                )
                session.add(batch)
                batches.append(batch)
            
            await session.flush()
            print(f"✅ Создано {len(batches)} партий")
            
            # 4. Движения склада БЕЗ performed_by (nullable)
            print("📊 Создание движений...")
            for batch in batches:
                movement = InventoryMovement(
                    flower_id=batch.flower_id,
                    batch_id=batch.id,
                    movement_type=MovementTypeEnum.purchase,
                    quantity=batch.quantity,
                    reason="Начальные остатки",
                    performed_by=None  # ← УБИРАЕМ ссылку на пользователя
                )
                session.add(movement)
            
            await session.commit()
            print("✅ Данные склада загружены успешно!")
            
            print(f"📊 Итого создано:")
            print(f"  Цветов: {len(flowers)}")
            print(f"  Поставщиков: {len(suppliers)}")
            print(f"  Партий: {len(batches)}")
            print(f"  Движений: {len(batches)}")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка загрузки данных: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(load_inventory_simple())