"""Базовые исключения приложения"""

class FlorangeException(Exception):
    """Базовое исключение приложения"""
    def __init__(self, message: str = "", code: str = "unknown"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class UserNotFoundError(FlorangeException):
    """Пользователь не найден"""
    def __init__(self, user_id: str):
        super().__init__(f"User {user_id} not found", "user_not_found")

class ProductNotFoundError(FlorangeException):
    """Товар не найден"""
    def __init__(self, product_id: int):
        super().__init__(f"Product {product_id} not found", "product_not_found")

class OrderNotFoundError(FlorangeException):
    """Заказ не найден"""
    def __init__(self, order_id: int):
        super().__init__(f"Order {order_id} not found", "order_not_found")

class ValidationError(FlorangeException):
    """Ошибка валидации данных"""
    pass

class PermissionDeniedError(FlorangeException):
    """Недостаточно прав доступа"""
    pass