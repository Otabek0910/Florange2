import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Flower Shop Bot"
    VERSION: str = "1.0.0"
    TELEGRAM_TOKEN: str = os.getenv("BOT_TOKEN")  # FIXED
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    FLORIST_CHANNEL_ID: str = os.getenv("FLORIST_CHANNEL_ID")

settings = Settings()