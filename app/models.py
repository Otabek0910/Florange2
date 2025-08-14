from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, ForeignKey, DateTime, Enum, Date  # ← ДОБАВИТЬ Date
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum
import sqlalchemy as sa

Base = declarative_base()

class RoleEnum(enum.Enum):
    client = "client"
    florist = "florist" 
    courier = "courier"
    owner = "owner"

class OrderStatusEnum(enum.Enum):
    new = "new"
    await_florist = "await_florist"
    accepted = "accepted"
    preparing = "preparing"
    ready = "ready"
    delivering = "delivering"
    delivered = "delivered"
    canceled = "canceled"

class InventoryOpEnum(enum.Enum):
    incoming = "incoming"
    sale = "sale"
    loss = "loss"
    correction = "correction"

class RequestedRoleEnum(enum.Enum):
    florist = "florist"
    owner = "owner"

class RequestStatusEnum(enum.Enum):
    pending = "pending"
    approved = "approved" 
    rejected = "rejected"

class ConsultationStatusEnum(enum.Enum):
    active = "active"
    completed_by_client = "completed_by_client"
    completed_by_florist = "completed_by_florist"
    expired = "expired"

class SupplyStatusEnum(enum.Enum):
    pending = "pending"      # Создан флористом
    approved = "approved"    # Одобрен владельцем  
    ordered = "ordered"      # Отправлен поставщику
    delivered = "delivered"  # Доставлен на склад
    rejected = "rejected"    # Отклонен

class MovementTypeEnum(enum.Enum):
    purchase = "purchase"    # Поступление от поставщика
    sale = "sale"           # Списание при продаже
    loss = "loss"           # Потеря/порча
    expired = "expired"     # Просрочка
    correction = "correction" # Корректировка остатков
    return_supplier = "return_supplier" # Возврат поставщику


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_id = Column(String(50), unique=True, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    lang = Column(String(5))
    role = Column(Enum(RoleEnum), default=RoleEnum.client)
    created_at = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name_ru = Column(String(255), nullable=False)
    name_uz = Column(String(255), nullable=False)
    sort = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    products = relationship("Product", back_populates="category")

    @property
    def name(self):
        return self.name_ru  # Для обратной совместимости

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name_ru = Column(String(255), nullable=False)
    name_uz = Column(String(255), nullable=False)
    desc_ru = Column(Text)
    desc_uz = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    photo_file_id = Column(String(255))
    photo_url = Column(String(500))
    stock_qty = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    category = relationship("Category", back_populates="products")

    @property
    def name(self):
        return self.name_ru  # Для обратной совместимости
    
    @property 
    def description(self):
        return self.desc_ru  # Для обратной совместимости

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    florist_id = Column(Integer, ForeignKey("users.id"))  # 🆕 КТО ПРИНЯЛ ЗАКАЗ
    total_price = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(Enum(OrderStatusEnum), default=OrderStatusEnum.new)
    address = Column(Text)
    phone = Column(String(20))
    slot_at = Column(DateTime)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", foreign_keys=[user_id])
    florist = relationship("User", foreign_keys=[florist_id])  # 🆕
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    order = relationship("Order", back_populates="items")
    product = relationship("Product")

class InventoryLog(Base):
    __tablename__ = "inventory_log"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    op = Column(Enum(InventoryOpEnum), nullable=False)
    qty = Column(Integer, nullable=False)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    product = relationship("Product")

class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RoleRequest(Base):
    __tablename__ = "role_requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_tg_id = Column(String(50), nullable=False)  # 🆕 ОСНОВНОЙ КЛЮЧ
    requested_role = Column(Enum(RequestedRoleEnum), nullable=False)
    status = Column(Enum(RequestStatusEnum), default=RequestStatusEnum.pending)
    reason = Column(Text, default="Автоматическая заявка")
    
    # 🆕 СТРУКТУРИРОВАННЫЕ ПОЛЯ (вместо user_data)
    first_name = Column(String(100))
    last_name = Column(String(100))  
    phone = Column(String(20))
    lang = Column(String(5))
    
    approved_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approver = relationship("User", foreign_keys=[approved_by])

# ========== КОНСУЛЬТАЦИИ (ОСТАВЛЯЕМ КАК ЕСТЬ) ==========

class FloristProfile(Base):
    __tablename__ = "florist_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    bio = Column(Text, default="")
    specialization = Column(String(255), default="")
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    rating = Column(Numeric(3, 2), default=0.0)  # 0.00 до 5.00
    reviews_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User")

class Consultation(Base):
    __tablename__ = "consultations"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    florist_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(ConsultationStatusEnum), default=ConsultationStatusEnum.active)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    theme = Column(String(255))  # ИИ-генерируемая тема
    archive_id = Column(String(100))  # ID архива в канале
    created_at = Column(DateTime, default=datetime.utcnow)
    
    client = relationship("User", foreign_keys=[client_id])
    florist = relationship("User", foreign_keys=[florist_id])
    messages = relationship("ConsultationMessage", back_populates="consultation")

class ConsultationMessage(Base):
    __tablename__ = "consultation_messages"
    id = Column(Integer, primary_key=True)
    consultation_id = Column(Integer, ForeignKey("consultations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message_text = Column(Text)
    photo_file_id = Column(String(255))
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    consultation = relationship("Consultation", back_populates="messages")
    sender = relationship("User")

class FloristReview(Base):
    __tablename__ = "florist_reviews"
    id = Column(Integer, primary_key=True)
    consultation_id = Column(Integer, ForeignKey("consultations.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    florist_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 звезд
    created_at = Column(DateTime, default=datetime.utcnow)
    
    consultation = relationship("Consultation")
    client = relationship("User", foreign_keys=[client_id])
    florist = relationship("User", foreign_keys=[florist_id])

class Flower(Base):
    """Базовые цветы/материалы для букетов"""
    __tablename__ = "flowers"
    
    id = Column(Integer, primary_key=True)
    name_ru = Column(String(255), nullable=False)
    name_uz = Column(String(255), nullable=False)
    unit_type = Column(String(20), nullable=False)  # 'piece', 'bundle', 'kg'
    min_stock = Column(Integer, default=0)  # Минимальный остаток
    max_stock = Column(Integer, default=100)  # Максимальный остаток
    shelf_life_days = Column(Integer, default=7)  # Срок годности в днях
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    batches = relationship("InventoryBatch", back_populates="flower")
    movements = relationship("InventoryMovement", back_populates="flower")
    compositions = relationship("ProductComposition", back_populates="flower")

class Supplier(Base):
    """Поставщики цветов"""
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    contact_person = Column(String(255))
    phone = Column(String(20))
    email = Column(String(255))
    rating = Column(Numeric(3, 2), default=0.0)  # Рейтинг 0.00-5.00
    is_active = Column(Boolean, default=True)
    notes = Column(Text)  # Примечания
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    supply_orders = relationship("SupplyOrder", back_populates="supplier")
    batches = relationship("InventoryBatch", back_populates="supplier")

class SupplyOrder(Base):
    """Заказы поставщикам"""
    __tablename__ = "supply_orders"
    
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    florist_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(SupplyStatusEnum), default=SupplyStatusEnum.pending)
    total_amount = Column(Numeric(10, 2), default=0)
    notes = Column(Text)  # Комментарий флориста
    delivery_date = Column(Date)  # Планируемая дата доставки
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)
    approved_by = Column(Integer, ForeignKey("users.id"))
    
    # Связи
    supplier = relationship("Supplier", back_populates="supply_orders")
    florist = relationship("User", foreign_keys=[florist_id])
    approver = relationship("User", foreign_keys=[approved_by])
    items = relationship("SupplyItem", back_populates="supply_order", cascade="all, delete-orphan")

class SupplyItem(Base):
    """Позиции в заказе поставщику"""
    __tablename__ = "supply_items"
    
    id = Column(Integer, primary_key=True)
    supply_order_id = Column(Integer, ForeignKey("supply_orders.id"), nullable=False)
    flower_id = Column(Integer, ForeignKey("flowers.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    
    # Связи
    supply_order = relationship("SupplyOrder", back_populates="items")
    flower = relationship("Flower")

class InventoryBatch(Base):
    """Партии товаров на складе"""
    __tablename__ = "inventory_batches"
    
    id = Column(Integer, primary_key=True)
    flower_id = Column(Integer, ForeignKey("flowers.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    quantity = Column(Integer, nullable=False)
    purchase_price = Column(Numeric(10, 2))  # Закупочная цена за единицу
    batch_date = Column(Date, default=datetime.utcnow().date)
    expire_date = Column(Date)  # Дата истечения срока годности
    supply_order_id = Column(Integer, ForeignKey("supply_orders.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    flower = relationship("Flower", back_populates="batches")
    supplier = relationship("Supplier", back_populates="batches")
    supply_order = relationship("SupplyOrder")
    movements = relationship("InventoryMovement", back_populates="batch")

class InventoryMovement(Base):
    """Движения по складу"""
    __tablename__ = "inventory_movements"
    
    id = Column(Integer, primary_key=True)
    flower_id = Column(Integer, ForeignKey("flowers.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("inventory_batches.id"))
    movement_type = Column(Enum(MovementTypeEnum), nullable=False)
    quantity = Column(Integer, nullable=False)  # + приход, - расход
    order_id = Column(Integer, ForeignKey("orders.id"))  # Для списания при продаже
    supply_order_id = Column(Integer, ForeignKey("supply_orders.id"))  # Для поступлений
    reason = Column(Text)  # Причина движения
    performed_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    flower = relationship("Flower", back_populates="movements")
    batch = relationship("InventoryBatch", back_populates="movements")
    order = relationship("Order")
    supply_order = relationship("SupplyOrder")
    performer = relationship("User")

class ProductComposition(Base):
    """Состав продуктов (рецепты букетов)"""
    __tablename__ = "product_compositions"
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    flower_id = Column(Integer, ForeignKey("flowers.id"), nullable=False)
    quantity = Column(Integer, nullable=False)  # Количество цветов в букете
    is_required = Column(Boolean, default=True)  # Обязательный компонент или опциональный
    
    # Связи
    product = relationship("Product")
    flower = relationship("Flower", back_populates="compositions")
    