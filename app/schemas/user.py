from typing import Optional
from pydantic import BaseModel
from app.models import RoleEnum

class UserBase(BaseModel):
    """Базовая схема пользователя"""
    tg_id: str
    first_name: Optional[str] = None
    phone: Optional[str] = None
    lang: str = "ru"

class UserCreate(UserBase):
    """Создание пользователя"""
    role: RoleEnum = RoleEnum.client

class UserUpdate(BaseModel):
    """Обновление пользователя"""
    first_name: Optional[str] = None
    phone: Optional[str] = None
    lang: Optional[str] = None
    role: Optional[RoleEnum] = None

class UserResponse(UserBase):
    """Ответ с данными пользователя"""
    id: int
    role: RoleEnum
    
    class Config:
        from_attributes = True