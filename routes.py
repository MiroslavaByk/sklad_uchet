from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from crud import *
from schemas import *
from exchange_manager import (
    build_incoming_xml, build_outgoing_xml, save_to_1c_file,
    get_exchange_files
)
import os
import logging

# Настройка логирования
logging.basicConfig(
    filename='app.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

router = APIRouter()


# ==================== ТОВАРЫ ====================

@router.get("/products", response_model=list[ProductResponse])
def get_products_route(
        archived: bool = False,
        search: str = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """Получить список товаров с возможностью фильтрации и поиска"""
    try:
        products = get_products(db, archived, skip, limit, search)
        result = []
        for p in products:
            stock = get_stock_by_product(db, p.id)
            result.append(ProductResponse(
                id=p.id,
                name=p.name,
                sku=p.sku,
                unit=p.unit,
                min_stock=p.min_stock,
                is_archived=p.is_archived,
                current_stock=stock.quantity if stock else 0
            ))
        return result
    except Exception as e:
        logging.error(f"Ошибка в get_products_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products", response_model=ProductResponse)
def create_product_route(product: ProductCreate, db: Session = Depends(get_db)):
    """Создать новый товар"""
    try:
        if not product.name or len(product.name.strip()) == 0:
            raise HTTPException(status_code=400, detail="Наименование товара не может быть пустым")
        if not product.unit or len(product.unit.strip()) == 0:
            raise HTTPException(status_code=400, detail="Единица измерения не может быть пустой")
        if product.min_stock < 0:
            raise HTTPException(status_code=400, detail="Минимальный остаток не может быть отрицательным")

        result = create_product(db, product)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в create_product_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/products/{product_id}")
def update_product_route(product_id: int, product: ProductUpdate, db: Session = Depends(get_db)):
    """Обновить данные товара"""
    try:
        result = update_product(db, product_id, product)
        if not result:
            raise HTTPException(status_code=404, detail="Товар не найден")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в update_product_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}")
def archive_product_route(product_id: int, db: Session = Depends(get_db)):
    """Архивировать товар (мягкое удаление)"""
    try:
        result = archive_product(db, product_id)
        if not result:
            raise HTTPException(status_code=404, detail="Товар не найден")
        return {"message": "Товар архивирован"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в archive_product_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ПОСТУПЛЕНИЯ ====================

@router.post("/incoming")
def create_incoming_route(incoming: IncomingCreate, db: Session = Depends(get_db)):
    """Создать операцию поступления"""
    try:
        if incoming.quantity <= 0:
            raise HTTPException(status_code=400, detail="Количество должно быть больше 0")
        if incoming.price <= 0:
            raise HTTPException(status_code=400, detail="Цена должна быть больше 0")

        result = create_incoming(db, incoming)
        return {"message": "Поступление добавлено", "id": result.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в create_incoming_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incoming")
def get_incoming_route(
        product_id: int = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """Получить список операций поступления"""
    try:
        return get_incoming(db, product_id, skip, limit)
    except Exception as e:
        logging.error(f"Ошибка в get_incoming_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== СПИСАНИЯ ====================

@router.post("/outgoing")
def create_outgoing_route(outgoing: OutgoingCreate, db: Session = Depends(get_db)):
    """Создать операцию списания"""
    try:
        if outgoing.quantity <= 0:
            raise HTTPException(status_code=400, detail="Количество должно быть больше 0")

        result = create_outgoing(db, outgoing)
        return {"message": "Списание выполнено", "id": result.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в create_outgoing_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/outgoing")
def get_outgoing_route(
        product_id: int = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """Получить список операций списания"""
    try:
        return get_outgoing(db, product_id, skip, limit)
    except Exception as e:
        logging.error(f"Ошибка в get_outgoing_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ОСТАТКИ ====================

@router.get("/stocks")
def get_stocks_route(db: Session = Depends(get_db)):
    """Получить текущие остатки всех товаров"""
    try:
        stocks = get_stocks(db)
        return [
            {
                "product_id": s.Stock.product_id,
                "product_name": s.Product.name,
                "quantity": s.Stock.quantity,
                "avg_price": s.Stock.avg_price
            }
            for s in stocks
        ]
    except Exception as e:
        logging.error(f"Ошибка в get_stocks_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ОТЧЁТЫ ====================

@router.get("/reports/movement")
def get_movement_report_route(
        product_id: int,
        start_date: str,
        end_date: str,
        db: Session = Depends(get_db)
):
    """Отчёт о движении товара за период"""
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        if start > end:
            raise HTTPException(status_code=400, detail="Дата начала не может быть позже даты окончания")

        report = get_movement_report(db, product_id, start, end)
        return report
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DDTHH:MM:SS")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в get_movement_report_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/critical")
def get_critical_stocks_route(db: Session = Depends(get_db)):
    """Отчёт по товарам с остатком ниже минимального"""
    try:
        return get_critical_stocks(db)
    except Exception as e:
        logging.error(f"Ошибка в get_critical_stocks_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ИНТЕГРАЦИЯ С 1С ====================

@router.post("/integration/export-incoming/{incoming_id}")
def export_incoming_to_1c(incoming_id: int, db: Session = Depends(get_db)):
    """Экспортирует операцию поступления в XML для 1С"""
    try:
        incoming = db.query(Incoming).filter(Incoming.id == incoming_id).first()
        if not incoming:
            raise HTTPException(status_code=404, detail="Операция не найдена")

        product = db.query(Product).filter(Product.id == incoming.product_id).first()
        product_name = product.name if product else "Неизвестно"

        xml_content = build_incoming_xml(
            product_id=incoming.product_id,
            product_name=product_name,
            quantity=incoming.quantity,
            price=incoming.price,
            supplier=incoming.supplier or ""
        )

        filename = f"incoming_{incoming_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        save_to_1c_file(filename, xml_content)

        return {"message": "Операция экспортирована в 1С", "file": filename}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в export_incoming_to_1c: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/integration/export-outgoing/{outgoing_id}")
def export_outgoing_to_1c(outgoing_id: int, db: Session = Depends(get_db)):
    """Экспортирует операцию списания в XML для 1С"""
    try:
        outgoing = db.query(Outgoing).filter(Outgoing.id == outgoing_id).first()
        if not outgoing:
            raise HTTPException(status_code=404, detail="Операция не найдена")

        product = db.query(Product).filter(Product.id == outgoing.product_id).first()
        product_name = product.name if product else "Неизвестно"

        xml_content = build_outgoing_xml(
            product_id=outgoing.product_id,
            product_name=product_name,
            quantity=outgoing.quantity,
            reason=outgoing.reason,
            recipient=outgoing.recipient or ""
        )

        filename = f"outgoing_{outgoing_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        save_to_1c_file(filename, xml_content)

        return {"message": "Операция экспортирована в 1С", "file": filename}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Ошибка в export_outgoing_to_1c: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/integration/files")
def get_exchange_files_route():
    """Возвращает список файлов в каталогах обмена"""
    try:
        return get_exchange_files()
    except Exception as e:
        logging.error(f"Ошибка в get_exchange_files_route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))