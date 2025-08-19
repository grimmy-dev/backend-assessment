from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date as Date
from enum import Enum


class StorageType(str, Enum):
    MEMORY = "memory"
    DATABASE = "database"


class SalesData(BaseModel):
    date: Optional[Date] = None
    product: str = ""
    category: str = ""
    sales_amount: float = 0.0
    quantity: int = 0
    region: str = ""


class Article(BaseModel):
    id: int
    title: str
    content: str
    article_type: str
    generated_date: Date
    created_at: datetime


class DataSummary(BaseModel):
    total_sales: float
    average_sales: float
    record_count: int
    top_products: List[Dict[str, Any]]
    unique_products: int
    unique_regions: int
    date_range: Optional[Dict[str, str]] = None


class UploadResponse(BaseModel):
    status: str
    rows_processed: int
    rows_stored: int
    summary: DataSummary
    insights: List[str]
    file_hash: str
    duplicate_upload: bool = False


class GenerationResponse(BaseModel):
    status: str
    articles_generated: int
    articles: List[Article]
    generation_date: str
    data_summary: DataSummary
