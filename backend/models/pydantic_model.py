# app/models/pydantic_model.py
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid

class ConversationStage(str, Enum):
    DISCOVERY = "discovery"
    QUOTE = "quote"

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class MessageIn(BaseModel):
    session_id: Optional[str] = None
    content: str
    role: str = Field(..., pattern="^(user|assistant)$")

class MessageOut(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationState(BaseModel):
    session_id: uuid.UUID
    stage: ConversationStage = ConversationStage.DISCOVERY
    discovered_requirements: Dict[str, Any] = {}
    selected_products: List[Dict[str, Any]] = []
    total_price: float = 0.0
    
class ProductMatch(BaseModel):
    name: str
    description: Optional[str] = ""
    price: Optional[float] = 0.0
    score: Optional[float] = 0.0
    
class IntentClassification(BaseModel):
    intent: str  # "product_search", "requirement_clarification", "quote_request", "general"
    confidence: float
    entities: Dict[str, str] = {}

class ConversationResponse(BaseModel):
    message: str
    stage: ConversationStage
    products: List[ProductMatch] = []
    next_questions: List[str] = []

class QuotationItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: float

class Quotation(BaseModel):
    selected_products: List[QuotationItem]
    total: float
    generated_at: datetime | None = None

