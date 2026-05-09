from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from crud import *
from schemas import *
from exchange_manager import (
    build_incoming_xml, build_outgoing_xml, save_to_1c_file,
    parse_stock_from_1c, parse_products_from_1c, get_exchange_files
)
import os

router = APIRouter()


# === Товары ===
@router.get("/products", response_model=list[ProductResponse])
def get_products_route(archived: bool = False, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = get_products(db, archived, skip, limit)
    result = []
    for p in products:
        stock = get_stock_by_product(db, p.id)
        result.append(ProductResponse(
            id=p.id, name=p.name, sku=p.sku, unit=p.unit,
            min_stock=p.min_stock, is_archived=p.is_archived,
            current_stock=stock.quantity if stock else 0
        ))
    return result


@router.post("/products", response_model=ProductResponse)
def create_product_route(product: ProductCreate, db: Session = Depends(get_db)):
    return create_product(db, product)


@router.put("/products/{product_id}")
def update_product_route(product_id: int, product: ProductUpdate, db: Session = Depends(get_db)):
    result = update_product(db, product_id, product)
    if not result:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return result


@router.delete("/products/{product_id}")
def archive_product_route(product_id: int, db: Session = Depends(get_db)):
    result = archive_product(db, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return {"message": "Товар архивирован"}


# === Поступления ===
@router.post("/incoming")
def create_incoming_route(incoming: IncomingCreate, db: Session = Depends(get_db)):
    try:
        result = create_incoming(db, incoming)
        return {"message": "Поступление добавлено", "id": result.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/incoming")
def get_incoming_route(product_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_incoming(db, product_id, skip, limit)


# === Списания ===
@router.post("/outgoing")
def create_outgoing_route(outgoing: OutgoingCreate, db: Session = Depends(get_db)):
    try:
        result = create_outgoing(db, outgoing)
        return {"message": "Списание выполнено", "id": result.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/outgoing")
def get_outgoing_route(product_id: int = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_outgoing(db, product_id, skip, limit)


# === Остатки ===
@router.get("/stocks")
def get_stocks_route(db: Session = Depends(get_db)):
    stocks = get_stocks(db)
    return [{"product_id": s.Stock.product_id, "product_name": s.Product.name, "quantity": s.Stock.quantity} for s in
            stocks]


# === Отчёты ===
@router.get("/reports/movement")
def get_movement_report_route(product_id: int, start_date: str, end_date: str, db: Session = Depends(get_db)):
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        report = get_movement_report(db, product_id, start, end)
        return report
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== ИНТЕГРАЦИЯ С 1С =====

@router.post("/integration/export-incoming/{incoming_id}")
def export_incoming_to_1c(incoming_id: int, db: Session = Depends(get_db)):
    """Экспортирует операцию поступления в XML для 1С"""
    incoming = db.query(Incoming).filter(Incoming.id == incoming_id).first()
    if not incoming:
        raise HTTPException(status_code=404, detail="Операция не найдена")

    product = db.query(Product).filter(Product.id == incoming.product_id).first()

    xml_content = build_incoming_xml(
        product_id=incoming.product_id,
        product_name=product.name if product else "Неизвестно",
        quantity=incoming.quantity,
        price=incoming.price,
        supplier=incoming.supplier or ""
    )

    filename = f"incoming_{incoming_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
    save_to_1c_file(filename, xml_content)

    return {"message": "Операция экспортирована в 1С", "file": filename}


@router.post("/integration/export-outgoing/{outgoing_id}")
def export_outgoing_to_1c(outgoing_id: int, db: Session = Depends(get_db)):
    """Экспортирует операцию списания в XML для 1С"""
    outgoing = db.query(Outgoing).filter(Outgoing.id == outgoing_id).first()
    if not outgoing:
        raise HTTPException(status_code=404, detail="Операция не найдена")

    product = db.query(Product).filter(Product.id == outgoing.product_id).first()

    xml_content = build_outgoing_xml(
        product_id=outgoing.product_id,
        product_name=product.name if product else "Неизвестно",
        quantity=outgoing.quantity,
        reason=outgoing.reason,
        recipient=outgoing.recipient or ""
    )

    filename = f"outgoing_{outgoing_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
    save_to_1c_file(filename, xml_content)

    return {"message": "Операция экспортирована в 1С", "file": filename}


@router.get("/integration/files")
def get_exchange_files_route():
    """Возвращает список файлов в каталогах обмена"""
    return get_exchange_files()