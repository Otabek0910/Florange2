import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Flower Shop Bot"
    VERSION: str = "1.0.0"
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "8330017511:AAGimZfNnUwrv4mfjMPxxzYC5ks1OjUlY6Q")

settings = Settings()
