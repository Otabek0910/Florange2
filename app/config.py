# app/config.py - создать новый файл
import os
from dotenv import load_dotenv

def load_environment():
    """Безопасная загрузка переменных окружения"""
    
    # Приоритет: .env.development -> .env -> переменные системы
    if os.path.exists('.env.development'):
        load_dotenv('.env.development')
        print("🔧 Загружен .env.development (локальная разработка)")
    elif os.path.exists('.env'):
        load_dotenv('.env')
        print("📄 Загружен .env (template)")
    else:
        print("☁️ Используются системные переменные (GitHub Actions)")

class Config:
    """Конфигурация приложения"""
    
    def __init__(self):
        load_environment()
        
        # Обязательные переменные
        self.BOT_TOKEN = self._get_required("BOT_TOKEN")
        self.DATABASE_URL = self._get_required("DATABASE_URL")
        
        # Опциональные с defaults
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.ENV = os.getenv("ENV", "development")
        self.AI_PROVIDER = os.getenv("AI_PROVIDER", "yandex")
        
        # AI ключи
        self.YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")
        
        # Каналы
        self.FLORIST_CHANNEL_ID = os.getenv("FLORIST_CHANNEL_ID")
        self.ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")
        
        # Webhook
        self.WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    
    def _get_required(self, key: str) -> str:
        """Получить обязательную переменную"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Переменная {key} обязательна")
        return value
    
    def is_development(self) -> bool:
        return self.ENV == "development"
    
    def validate(self):
        """Валидация конфигурации"""
        if self.is_development():
            print("🔧 Режим разработки")
        else:
            print("🚀 Продакшн режим")
            
        # Проверка AI
        if not self.YANDEX_GPT_API_KEY:
            print("⚠️ YANDEX_GPT_API_KEY не установлен")

# Глобальный экземпляр
config = Config()

# Обратная совместимость для старого кода
settings = config
