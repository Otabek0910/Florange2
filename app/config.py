import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Настройки приложения"""
    PROJECT_NAME: str = "Flower Shop Bot"
    VERSION: str = "1.0.0"

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    WEBHOOK_URL: Optional[str] = os.getenv("WEBHOOK_URL")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Notifications
    FLORIST_CHANNEL_ID: Optional[str] = os.getenv("FLORIST_CHANNEL_ID")

    # Archive & AI
    ARCHIVE_CHANNEL_ID: Optional[str] = os.getenv("ARCHIVE_CHANNEL_ID")
    
    YANDEX_GPT_API_KEY: Optional[str] = os.getenv("YANDEX_GPT_API_KEY")
    YANDEX_FOLDER_ID: Optional[str] = os.getenv("YANDEX_FOLDER_ID")
    
    # Payment
    CLICK_MERCHANT_ID: Optional[str] = os.getenv("CLICK_MERCHANT_ID")
    PAYME_MERCHANT_ID: Optional[str] = os.getenv("PAYME_MERCHANT_ID")

    def validate_channel(self) -> bool:
        """Проверить настройки канала"""
        if not self.FLORIST_CHANNEL_ID:
            print("⚠️ FLORIST_CHANNEL_ID не настроен")
            return False
        if not self.FLORIST_CHANNEL_ID.startswith("-"):
            print(f"⚠️ FLORIST_CHANNEL_ID должен начинаться с '-': {self.FLORIST_CHANNEL_ID}")
            return False
        return True

settings = Settings()
