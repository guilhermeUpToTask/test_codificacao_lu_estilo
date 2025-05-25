from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID
from sqlmodel import select
from app.api.deps import SessionDep, CurrentUser
from app.models.order import (
    Order,
    OrderCreate,
    OrderRead,
    OrderUpdate,
    OrderItem,
)
from app.models.product import Product

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/", response_model=List[OrderRead], dependencies=[Depends(CurrentUser)])
def list_orders(
    *,
    session: SessionDep,
    # Filters
    start_date: Optional[date] = Query(None, description="Start of order period"),
    end_date: Optional[date] = Query(None, description="End of order period"),
    section: Optional[str] = Query(None, description="Filter by product section"),
    order_id: Optional[UUID] = Query(None, description="Filter by order ID"),
    status: Optional[str] = Query(None, description="Filter by order status"),
    client_id: Optional[UUID] = Query(None, description="Filter by client ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
):
    query = select(Order)
    if start_date:
        query = query.where(Order.order_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(Order.order_date <= datetime.combine(end_date, datetime.max.time()))
    if order_id:
        query = query.where(Order.id == order_id)
    if status:
        query = query.where(Order.status == status)
    if client_id:
        query = query.where(Order.client_id == client_id)
    if section:
        # Join with items to filter by product section
        query = query.join(Order.items).where(OrderItem.section == section)

    return session.exec(query.offset(skip).limit(limit)).all()


@router.post(
    "/",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(CurrentUser)],
)
def create_order(
    *,
    session: SessionDep,
    order_in: OrderCreate,
):
    # Validate stock availability
    for item in order_in.items:
        product = session.get(Product, item.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.initial_stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {item.product_id}",
            )

    # Create order
    db_order = Order(client_id=order_in.client_id)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)

    # Deduct stock and create items
    for item in order_in.items:
        # Deduct
        product = session.get(Product, item.product_id)
        product.initial_stock -= item.quantity
        session.add(product)
        # Create item
        order_item = OrderItem(
            order_id=db_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            section=item.section,
        )
        session.add(order_item)
    session.commit()
    session.refresh(db_order)

    return db_order


@router.get("/{order_id}", response_model=OrderRead, dependencies=[Depends(CurrentUser)])
def read_order(
    *,
    session: SessionDep,
    order_id: UUID,
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/{order_id}", response_model=OrderRead, dependencies=[Depends(CurrentUser)])
def update_order(
    *,
    session: SessionDep,
    order_id: UUID,
    order_up: OrderUpdate,
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order_up.status:
        order.status = order_up.status
    order.updated_at = datetime.utcnow()

    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(CurrentUser)])
def delete_order(
    *,
    session: SessionDep,
    order_id: UUID,
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    session.delete(order)
    session.commit()
    return order
