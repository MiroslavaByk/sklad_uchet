import xml.etree.ElementTree as ET
import os
from datetime import datetime

EXCHANGE_DIR = "exchange/"
TO_1C_DIR = os.path.join(EXCHANGE_DIR, "to_1c")
FROM_1C_DIR = os.path.join(EXCHANGE_DIR, "from_1c")


def build_incoming_xml(product_id: int, product_name: str, quantity: int, price: float, supplier: str):
    """Формирует XML-запрос для создания документа поступления в 1С"""
    root = ET.Element("IncomingOrder")
    ET.SubElement(root, "product_id").text = str(product_id)
    ET.SubElement(root, "product_name").text = product_name
    ET.SubElement(root, "quantity").text = str(quantity)
    ET.SubElement(root, "price").text = str(price)
    ET.SubElement(root, "supplier").text = supplier
    ET.SubElement(root, "date").text = datetime.now().isoformat()

    return ET.tostring(root, encoding="utf-8", method="xml")


def save_to_1c_file(filename: str, content: bytes):
    """Сохраняет XML-файл в каталог для 1С"""
    os.makedirs(TO_1C_DIR, exist_ok=True)
    filepath = os.path.join(TO_1C_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)


def parse_stock_from_1c(filepath: str):
    """Читает XML-файл с остатками из 1С"""
    tree = ET.parse(filepath)
    root = tree.getroot()
    stocks = []
    for item in root.findall("item"):
        stocks.append({
            "product_id": int(item.find("product_id").text),
            "quantity": int(item.find("quantity").text)
        })
    return stocks


def build_outgoing_xml(product_id: int, product_name: str, quantity: int, reason: str, recipient: str):
    """Формирует XML-запрос для создания документа списания в 1С"""
    root = ET.Element("OutgoingOrder")
    ET.SubElement(root, "product_id").text = str(product_id)
    ET.SubElement(root, "product_name").text = product_name
    ET.SubElement(root, "quantity").text = str(quantity)
    ET.SubElement(root, "reason").text = reason
    ET.SubElement(root, "recipient").text = recipient or ""
    ET.SubElement(root, "date").text = datetime.now().isoformat()

    return ET.tostring(root, encoding="utf-8", method="xml")


def parse_products_from_1c(filepath: str):
    """Читает XML-файл со справочником товаров из 1С"""
    tree = ET.parse(filepath)
    root = tree.getroot()
    products = []
    for item in root.findall("product"):
        products.append({
            "id": int(item.find("id").text),
            "name": item.find("name").text,
            "sku": item.find("sku").text,
            "unit": item.find("unit").text
        })
    return products


def get_exchange_files():
    """Возвращает список файлов в каталогах обмена"""
    os.makedirs(TO_1C_DIR, exist_ok=True)
    os.makedirs(FROM_1C_DIR, exist_ok=True)

    to_1c_files = os.listdir(TO_1C_DIR)
    from_1c_files = os.listdir(FROM_1C_DIR)

    return {
        "to_1c": to_1c_files,
        "from_1c": from_1c_files
    }