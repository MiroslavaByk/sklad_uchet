from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from models import Product, Incoming, Outgoing, Stock, User
from schemas import ProductCreate, ProductUpdate, IncomingCreate, OutgoingCreate
import bcrypt


# === Товары ===
def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()


def get_products(db: Session, archived: bool = False, skip: int = 0, limit: int = 100):
    query = db.query(Product)
    if not archived:
        query = query.filter(Product.is_archived == False)
    return query.offset(skip).limit(limit).all()


def create_product(db: Session, product: ProductCreate):
    # Генерация артикула, если не указан
    if not product.sku:
        product.sku = f"SKU_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    db_product = Product(
        name=product.name,
        sku=product.sku,
        unit=product.unit,
        min_stock=product.min_stock
    )
    db.add(db_product)
    db.flush()

    # Создаём запись остатка для нового товара
    db_stock = Stock(product_id=db_product.id, quantity=0)
    db.add(db_stock)
    db.commit()
    db.refresh(db_product)
    return db_product


def update_product(db: Session, product_id: int, product_update: ProductUpdate):
    db_product = get_product(db, product_id)
    if not db_product:
        return None
    for key, value in product_update.dict(exclude_unset=True).items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    return db_product


def archive_product(db: Session, product_id: int):
    db_product = get_product(db, product_id)
    if db_product:
        db_product.is_archived = True
        db.commit()
    return db_product


# === Поступления ===
def create_incoming(db: Session, incoming: IncomingCreate):
    # Устанавливаем дату, если не указана
    date = incoming.date if incoming.date else datetime.now()

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
    if stock:
        stock.quantity += incoming.quantity
        # Пересчёт средней себестоимости
        total_value = stock.avg_price * (stock.quantity - incoming.quantity) + (incoming.price * incoming.quantity)
        if stock.quantity > 0:
            stock.avg_price = total_value / stock.quantity

    db.commit()
    db.refresh(db_incoming)
    return db_incoming


def get_incoming(db: Session, product_id: int = None, skip: int = 0, limit: int = 100):
    query = db.query(Incoming)
    if product_id:
        query = query.filter(Incoming.product_id == product_id)
    return query.order_by(Incoming.date.desc()).offset(skip).limit(limit).all()


# === Списания ===
def create_outgoing(db: Session, outgoing: OutgoingCreate):
    # Проверяем остаток
    stock = db.query(Stock).filter(Stock.product_id == outgoing.product_id).first()
    if not stock or stock.quantity < outgoing.quantity:
        raise ValueError(f"Недостаточно товара. Доступно: {stock.quantity if stock else 0}")

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

    db.commit()
    db.refresh(db_outgoing)
    return db_outgoing


def get_outgoing(db: Session, product_id: int = None, skip: int = 0, limit: int = 100):
    query = db.query(Outgoing)
    if product_id:
        query = query.filter(Outgoing.product_id == product_id)
    return query.order_by(Outgoing.date.desc()).offset(skip).limit(limit).all()


# === Остатки ===
def get_stocks(db: Session):
    return db.query(Stock, Product).join(Product, Stock.product_id == Product.id).filter(
        Product.is_archived == False).all()


def get_stock_by_product(db: Session, product_id: int):
    return db.query(Stock).filter(Stock.product_id == product_id).first()


# === Отчёты ===
def get_movement_report(db: Session, product_id: int, start_date: datetime, end_date: datetime):
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

    closing_stock = opening_stock + sum(i.quantity for i in incoming_period) - sum(o.quantity for o in outgoing_period)

    return {
        "product_id": product_id,
        "opening_stock": opening_stock,
        "total_incoming": sum(i.quantity for i in incoming_period),
        "total_outgoing": sum(o.quantity for o in outgoing_period),
        "closing_stock": closing_stock,
        "incoming_details": incoming_period,
        "outgoing_details": outgoing_period
    }