import os

from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://youtube.home")


class Config:
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
