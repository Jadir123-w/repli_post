import os
from dotenv import load_dotenv

# Solo carga el .env.local si estamos en desarrollo
if os.getenv("ENVIRONMENT", "local") == "local":
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", "config", ".env.local")
    dotenv_path = os.path.abspath(dotenv_path)

    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)


class Config:
    MARCELLA_GOOGLE_API_KEY = os.getenv("MARCELLA_GOOGLE_API_KEY")
    REPLI_MONGO_URI = os.getenv("REPLI_MONGO_URI")
    GMAIL_USER = os.getenv("GMAIL_USER")
    GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
    MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY")
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
