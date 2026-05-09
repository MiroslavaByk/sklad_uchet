from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Подключение к SQLite (файл базы данных создастся автоматически)
SQLALCHEMY_DATABASE_URL = "sqlite:///./sklad.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # нужно для SQLite
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Функция для получения сессии БД (для Dependency Injection в FastAPI)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()