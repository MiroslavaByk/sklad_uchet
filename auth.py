from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
import bcrypt
import logging
from database import get_db
from models import User
from schemas import UserCreate

# Настройка логирования
logging.basicConfig(
    filename='app.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

router = APIRouter()
security = HTTPBasic()


def hash_password(password: str) -> str:
    """Хеширует пароль с использованием bcrypt"""
    try:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    except Exception as e:
        logging.error(f"Ошибка в hash_password: {str(e)}")
        raise e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие пароля хешу"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        logging.error(f"Ошибка в verify_password: {str(e)}")
        return False


@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Регистрация нового пользователя

    - **username**: уникальное имя пользователя
    - **password**: пароль (минимум 3 символа)
    - **role**: роль (clerk, manager, admin) - по умолчанию clerk
    - **full_name**: полное имя (опционально)
    """
    try:
        # Валидация входных данных
        if not user.username or len(user.username.strip()) == 0:
            raise HTTPException(status_code=400, detail="Имя пользователя не может быть пустым")

        if not user.password or len(user.password) < 3:
            raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 3 символов")

        # Проверка допустимости роли
        allowed_roles = ["clerk", "manager", "admin"]
        if user.role not in allowed_roles:
            raise HTTPException(status_code=400, detail=f"Роль должна быть одной из: {', '.join(allowed_roles)}")

        # Проверка существования пользователя
        existing_user = db.query(User).filter(User.username == user.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")

        # Создание нового пользователя
        db_user = User(
            username=user.username,
            password_hash=hash_password(user.password),
            role=user.role,
            full_name=user.full_name
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        return {
            "message": "Пользователь успешно создан",
            "user_id": db_user.id,
            "username": db_user.username,
            "role": db_user.role
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в register: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.post("/login")
def login(credentials: HTTPBasicCredentials, db: Session = Depends(get_db)):
    """
    Вход в систему

    - **username**: имя пользователя
    - **password**: пароль
    """
    try:
        # Поиск пользователя в базе данных
        user = db.query(User).filter(User.username == credentials.username).first()

        # Проверка существования пользователя
        if not user:
            raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль")

        # Проверка пароля
        if not verify_password(credentials.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль")

        # Проверка активности учётной записи
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Учётная запись заблокирована. Обратитесь к администратору")

        return {
            "message": "Вход выполнен успешно",
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в login: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/me")
def get_current_user(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)):
    """
    Получить информацию о текущем авторизованном пользователе
    """
    try:
        user = db.query(User).filter(User.username == credentials.username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Пользователь не найден")

        if not verify_password(credentials.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверный пароль")

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "created_at": user.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в get_current_user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    """
    Получить список всех пользователей (только для администратора)
    Внимание: в реальном приложении здесь должна быть проверка прав доступа
    """
    try:
        users = db.query(User).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "full_name": u.full_name,
                "is_active": u.is_active,
                "created_at": u.created_at
            }
            for u in users
        ]
    except Exception as e:
        logging.error(f"Ошибка в get_all_users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/block")
def block_user(user_id: int, db: Session = Depends(get_db)):
    """
    Блокировка пользователя (только для администратора)
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        user.is_active = False
        db.commit()

        return {"message": f"Пользователь {user.username} заблокирован"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в block_user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/unblock")
def unblock_user(user_id: int, db: Session = Depends(get_db)):
    """
    Разблокировка пользователя (только для администратора)
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        user.is_active = True
        db.commit()

        return {"message": f"Пользователь {user.username} разблокирован"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в unblock_user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))