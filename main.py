from fastapi import FastAPI
from database import engine, Base
from routes import router as main_router
from auth import router as auth_router

# Создаём таблицы в БД
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Склад-Учёт", version="1.0")

# Подключаем маршруты
app.include_router(auth_router, prefix="/auth", tags=["Аутентификация"])
app.include_router(main_router, prefix="/api", tags=["API"])

@app.get("/")
def root():
    return {"message": "Склад-Учёт API работает"}

# ЗАПУСК СЕРВЕРА (добавь это!)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)