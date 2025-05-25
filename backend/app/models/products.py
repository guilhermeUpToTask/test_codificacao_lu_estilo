from typing import Optional, List
from datetime import date, datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship


class ProductBase(SQLModel):
    description: str = Field(..., description="Product description")
    sale_price: float = Field(..., ge=0, description="Sale price of the product")
    barcode: str = Field(..., index=True, description="Product barcode")
    section: str = Field(..., index=True, description="Store section or shelf location")
    category: Optional[str] = Field(None, index=True, description="Product category")
    initial_stock: int = Field(..., ge=0, description="Initial stock quantity")
    expiration_date: Optional[date] = Field(None, description="Expiration date, if applicable")


class Product(ProductBase, table=True):
    __tablename__ = "product"
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    images: List["ProductImage"] = Relationship(back_populates="product")


class ProductCreate(ProductBase):
    images: Optional[List[str]] = Field(default_factory=list, description="List of image URLs to attach to the product")


class ProductRead(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    images: List[str]


class ProductUpdate(SQLModel):
    description: Optional[str] = None
    sale_price: Optional[float] = Field(None, ge=0)
    barcode: Optional[str] = None
    section: Optional[str] = None
    category: Optional[str] = None
    initial_stock: Optional[int] = Field(None, ge=0)
    expiration_date: Optional[date] = None


class ProductImage(SQLModel, table=True):
    __tablename__ = "product_image"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id")
    url: str = Field(..., description="URL of the product image")

    product: "Product" = Relationship(back_populates="images")
