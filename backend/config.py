import os

from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "entrcol")
BATCH_SIZE = int(os.getenv("ETL_BATCH_SIZE", "1000"))

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-secret-key-32bytes")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "8"))
CAPTCHA_EXPIRATION_SECONDS = int(os.getenv("CAPTCHA_EXPIRATION_SECONDS", "240"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
