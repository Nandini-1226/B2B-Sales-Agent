# app/models/pydantic_model.py
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field

class MessageIn(BaseModel):
    session_id: str
    content: str
    role: str = Field(..., pattern="^(user|assistant)$")

class MessageOut(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        orm_mode = True

class QuotationItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: float

class Quotation(BaseModel):
    selected_products: List[QuotationItem]
    total: float
    generated_at: datetime | None = None

