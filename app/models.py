from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

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

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_id = Column(String(50), unique=True, nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))      # НОВОЕ ПОЛЕ
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
    total_price = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(Enum(OrderStatusEnum), default=OrderStatusEnum.new)
    address = Column(Text)
    phone = Column(String(20))
    slot_at = Column(DateTime)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")
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
    user_tg_id = Column(String(50), nullable=True)
    requested_role = Column(Enum(RequestedRoleEnum), nullable=False)
    status = Column(Enum(RequestStatusEnum), default=RequestStatusEnum.pending)
    reason = Column(Text, default="Автоматическая заявка")  # Дефолтное значение
    user_data = Column(Text)
    approved_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approver = relationship("User", foreign_keys=[approved_by])

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
    