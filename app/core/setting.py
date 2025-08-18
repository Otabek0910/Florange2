import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Telegram
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/diana")
    
    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

settings = Settings()