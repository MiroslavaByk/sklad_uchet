from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from models import Product, Incoming, Outgoing, Stock, User
from schemas import ProductCreate, ProductUpdate, IncomingCreate, OutgoingCreate
import bcrypt
import logging

# Настройка логирования
logging.basicConfig(
    filename='app.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ==================== ТОВАРЫ ====================

def get_product(db: Session, product_id: int):
    """Получить товар по ID"""
    try:
        return db.query(Product).filter(Product.id == product_id).first()
    except Exception as e:
        logging.error(f"Ошибка в get_product: {str(e)}")
        raise e


def get_products(db: Session, archived: bool = False, skip: int = 0, limit: int = 100, search: str = None):
    """Получить список товаров с фильтрацией и поиском"""
    try:
        query = db.query(Product)
        if not archived:
            query = query.filter(Product.is_archived == False)
        if search:
            query = query.filter(Product.name.contains(search))
        return query.offset(skip).limit(limit).all()
    except Exception as e:
        logging.error(f"Ошибка в get_products: {str(e)}")
        raise e


def create_product(db: Session, product: ProductCreate):
    """Создать новый товар"""
    try:
        # Генерация артикула, если не указан
        if not product.sku:
            product.sku = f"SKU_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Проверка на уникальность артикула
        existing = db.query(Product).filter(Product.sku == product.sku).first()
        if existing:
            raise ValueError(f"Товар с артикулом {product.sku} уже существует")

        db_product = Product(
            name=product.name,
            sku=product.sku,
            unit=product.unit,
            min_stock=product.min_stock or 0
        )
        db.add(db_product)
        db.flush()

        # Создаём запись остатка для нового товара
        db_stock = Stock(product_id=db_product.id, quantity=0)
        db.add(db_stock)
        db.commit()
        db.refresh(db_product)
        return db_product
    except ValueError as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в create_product: {str(e)}")
        raise Exception(f"Ошибка при создании товара: {str(e)}")


def update_product(db: Session, product_id: int, product_update: ProductUpdate):
    """Обновить данные товара"""
    try:
        db_product = get_product(db, product_id)
        if not db_product:
            raise ValueError(f"Товар с id={product_id} не найден")

        update_data = product_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_product, key, value)

        db.commit()
        db.refresh(db_product)
        return db_product
    except ValueError as e:
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в update_product: {str(e)}")
        raise Exception(f"Ошибка при обновлении товара: {str(e)}")


def archive_product(db: Session, product_id: int):
    """Мягкое удаление товара (архивация)"""
    try:
        db_product = get_product(db, product_id)
        if not db_product:
            raise ValueError(f"Товар с id={product_id} не найден")

        db_product.is_archived = True
        db.commit()
        return db_product
    except ValueError as e:
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в archive_product: {str(e)}")
        raise Exception(f"Ошибка при архивации товара: {str(e)}")


def restore_product(db: Session, product_id: int):
    """Восстановить товар из архива"""
    try:
        db_product = get_product(db, product_id)
        if not db_product:
            raise ValueError(f"Товар с id={product_id} не найден")

        db_product.is_archived = False
        db.commit()
        return db_product
    except ValueError as e:
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в restore_product: {str(e)}")
        raise Exception(f"Ошибка при восстановлении товара: {str(e)}")


# ==================== ОПЕРАЦИИ ПОСТУПЛЕНИЯ ====================

def create_incoming(db: Session, incoming: IncomingCreate):
    """Создать операцию поступления и обновить остаток"""
    try:
        # Валидация
        if incoming.quantity <= 0:
            raise ValueError("Количество должно быть больше 0")
        if incoming.price <= 0:
            raise ValueError("Цена должна быть больше 0")

        # Устанавливаем дату, если не указана
        date = incoming.date if incoming.date else datetime.now()

        # Проверка существования товара
        product = get_product(db, incoming.product_id)
        if not product:
            raise ValueError(f"Товар с id={incoming.product_id} не найден")

        db_incoming = Incoming(
            product_id=incoming.product_id,
            quantity=incoming.quantity,
            price=incoming.price,
            supplier=incoming.supplier,
            date=date
        )
        db.add(db_incoming)

        # Обновляем остаток
        stock = db.query(Stock).filter(Stock.product_id == incoming.product_id).first()
        if not stock:
            # Если записи остатка нет, создаём её
            stock = Stock(product_id=incoming.product_id, quantity=0)
            db.add(stock)

        stock.quantity += incoming.quantity
        stock.updated_at = datetime.now()

        db.commit()
        db.refresh(db_incoming)
        return db_incoming
    except ValueError as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в create_incoming: {str(e)}")
        raise Exception(f"Ошибка при создании поступления: {str(e)}")


def get_incoming(db: Session, product_id: int = None, skip: int = 0, limit: int = 100):
    """Получить список операций поступления"""
    try:
        query = db.query(Incoming)
        if product_id:
            query = query.filter(Incoming.product_id == product_id)
        return query.order_by(Incoming.date.desc()).offset(skip).limit(limit).all()
    except Exception as e:
        logging.error(f"Ошибка в get_incoming: {str(e)}")
        raise e


# ==================== ОПЕРАЦИИ СПИСАНИЯ ====================

def create_outgoing(db: Session, outgoing: OutgoingCreate):
    """Создать операцию списания и обновить остаток"""
    try:
        # Валидация
        if outgoing.quantity <= 0:
            raise ValueError("Количество должно быть больше 0")

        # Проверка остатка
        stock = db.query(Stock).filter(Stock.product_id == outgoing.product_id).first()
        if not stock:
            raise ValueError(f"Товар с id={outgoing.product_id} не найден в остатках")

        if stock.quantity < outgoing.quantity:
            raise ValueError(
                f"Недостаточно товара на складе. Доступно: {stock.quantity}, запрошено: {outgoing.quantity}")

        # Проверка существования товара
        product = get_product(db, outgoing.product_id)
        if not product:
            raise ValueError(f"Товар с id={outgoing.product_id} не найден")

        # Устанавливаем дату, если не указана
        date = outgoing.date if outgoing.date else datetime.now()

        db_outgoing = Outgoing(
            product_id=outgoing.product_id,
            quantity=outgoing.quantity,
            reason=outgoing.reason,
            recipient=outgoing.recipient,
            date=date
        )
        db.add(db_outgoing)

        # Обновляем остаток
        stock.quantity -= outgoing.quantity
        stock.updated_at = datetime.now()

        db.commit()
        db.refresh(db_outgoing)
        return db_outgoing
    except ValueError as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        logging.error(f"Ошибка в create_outgoing: {str(e)}")
        raise Exception(f"Ошибка при создании списания: {str(e)}")


def get_outgoing(db: Session, product_id: int = None, skip: int = 0, limit: int = 100):
    """Получить список операций списания"""
    try:
        query = db.query(Outgoing)
        if product_id:
            query = query.filter(Outgoing.product_id == product_id)
        return query.order_by(Outgoing.date.desc()).offset(skip).limit(limit).all()
    except Exception as e:
        logging.error(f"Ошибка в get_outgoing: {str(e)}")
        raise e


# ==================== ОСТАТКИ ====================

def get_stocks(db: Session):
    """Получить все остатки с информацией о товарах"""
    try:
        return db.query(Stock, Product).join(
            Product, Stock.product_id == Product.id
        ).filter(Product.is_archived == False).all()
    except Exception as e:
        logging.error(f"Ошибка в get_stocks: {str(e)}")
        raise e


def get_stock_by_product(db: Session, product_id: int):
    """Получить остаток по конкретному товару"""
    try:
        return db.query(Stock).filter(Stock.product_id == product_id).first()
    except Exception as e:
        logging.error(f"Ошибка в get_stock_by_product: {str(e)}")
        raise e


# ==================== ОТЧЁТЫ ====================

def get_movement_report(db: Session, product_id: int, start_date: datetime, end_date: datetime):
    """Сформировать отчёт о движении товара за период"""
    try:
        if start_date > end_date:
            raise ValueError("Дата начала не может быть позже даты окончания")

        # Проверка существования товара
        product = get_product(db, product_id)
        if not product:
            raise ValueError(f"Товар с id={product_id} не найден")

        # Начальный остаток (до start_date)
        incoming_before = db.query(Incoming).filter(
            Incoming.product_id == product_id,
            Incoming.date < start_date
        ).all()
        outgoing_before = db.query(Outgoing).filter(
            Outgoing.product_id == product_id,
            Outgoing.date < start_date
        ).all()
        opening_stock = sum(i.quantity for i in incoming_before) - sum(o.quantity for o in outgoing_before)

        # Операции за период
        incoming_period = db.query(Incoming).filter(
            Incoming.product_id == product_id,
            Incoming.date >= start_date,
            Incoming.date <= end_date
        ).all()
        outgoing_period = db.query(Outgoing).filter(
            Outgoing.product_id == product_id,
            Outgoing.date >= start_date,
            Outgoing.date <= end_date
        ).all()

        # Конечный остаток
        closing_stock = opening_stock + sum(i.quantity for i in incoming_period) - sum(
            o.quantity for o in outgoing_period)

        return {
            "product_id": product_id,
            "product_name": product.name,
            "opening_stock": opening_stock,
            "total_incoming": sum(i.quantity for i in incoming_period),
            "total_outgoing": sum(o.quantity for o in outgoing_period),
            "closing_stock": closing_stock,
            "incoming_details": [
                {"id": i.id, "date": i.date.isoformat(), "quantity": i.quantity, "price": i.price}
                for i in incoming_period
            ],
            "outgoing_details": [
                {"id": o.id, "date": o.date.isoformat(), "quantity": o.quantity, "reason": o.reason}
                for o in outgoing_period
            ]
        }
    except ValueError as e:
        raise e
    except Exception as e:
        logging.error(f"Ошибка в get_movement_report: {str(e)}")
        raise Exception(f"Ошибка при формировании отчёта: {str(e)}")


def get_critical_stocks(db: Session):
    """Возвращает товары с остатком ниже минимального"""
    try:
        results = db.query(Product, Stock).join(
            Stock, Product.id == Stock.product_id
        ).filter(
            Product.is_archived == False,
            Stock.quantity < Product.min_stock
        ).all()

        return [
            {
                "product_id": p.id,
                "product_name": p.name,
                "current_stock": s.quantity,
                "min_stock": p.min_stock,
                "deficit": p.min_stock - s.quantity
            }
            for p, s in results
        ]
    except Exception as e:
        logging.error(f"Ошибка в get_critical_stocks: {str(e)}")
        raise e