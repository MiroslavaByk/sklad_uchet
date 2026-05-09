from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Схемы для товара
class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    unit: str
    min_stock: Optional[int] = 0

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    min_stock: Optional[int] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    sku: str
    unit: str
    min_stock: int
    is_archived: bool
    current_stock: Optional[int] = 0

# Схемы для поступления
class IncomingCreate(BaseModel):
    product_id: int
    quantity: int
    price: float
    supplier: Optional[str] = None
    date: Optional[datetime] = None

class IncomingResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price: float
    supplier: Optional[str]
    date: datetime
    total: float

# Схемы для списания
class OutgoingCreate(BaseModel):
    product_id: int
    quantity: int
    reason: str
    recipient: Optional[str] = None
    date: Optional[datetime] = None

class OutgoingResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    reason: str
    recipient: Optional[str]
    date: datetime

# Схемы для пользователя
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "clerk"
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str