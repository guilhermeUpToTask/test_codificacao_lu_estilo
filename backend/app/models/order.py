from typing import List, Optional
from datetime import datetime, date
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship


class OrderBase(SQLModel):
    client_id: UUID = Field(..., foreign_key="client.id", description="ID of the client placing the order")
    order_date: datetime = Field(default_factory=datetime.utcnow, description="Date and time when order was placed")
    status: str = Field(default="pending", description="Status of the order, e.g., pending, shipped, delivered")


class Order(OrderBase, table=True):
    __tablename__ = "order"
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    items: List["OrderItem"] = Relationship(back_populates="order")


class OrderCreate(SQLModel):
    client_id: UUID
    items: List["OrderItemCreate"]


class OrderRead(OrderBase):
    id: UUID
    order_date: datetime
    status: str
    items: List["OrderItemRead"]


class OrderUpdate(SQLModel):
    status: Optional[str] = None


class OrderItemBase(SQLModel):
    product_id: UUID = Field(..., foreign_key="product.id", description="ID of the product")
    quantity: int = Field(..., ge=1, description="Quantity of the product ordered")
    unit_price: float = Field(..., ge=0, description="Sale price at time of order")
    section: Optional[str] = Field(None, description="Store section for filtering")


class OrderItem(OrderItemBase, table=True):
    __tablename__ = "order_item"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="order.id")
    order: "Order" = Relationship(back_populates="items")


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemRead(OrderItemBase):
    id: UUID
