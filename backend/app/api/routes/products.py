from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from uuid import UUID
from sqlmodel import select

from app.api.deps import SessionDep, CurrentUser
from app.models.product import (
    Product,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ProductImage,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/", response_model=List[ProductRead], dependencies=[Depends(CurrentUser)])
def list_products(
    *,
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    available: Optional[bool] = Query(None),
):
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    if min_price is not None:
        query = query.where(Product.sale_price >= min_price)
    if max_price is not None:
        query = query.where(Product.sale_price <= max_price)
    if available is True:
        query = query.where(Product.initial_stock > 0)
    elif available is False:
        query = query.where(Product.initial_stock <= 0)

    return session.exec(query.offset(skip).limit(limit)).all()


@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(CurrentUser)],
)
def create_product(
    *,
    session: SessionDep,
    product_in: ProductCreate,
):
    # Validate unique barcode
    existing = session.exec(select(Product).where(Product.barcode == product_in.barcode)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Barcode already in use")

    db_product = Product.model_validate(product_in)
    session.add(db_product)
    session.commit()
    session.refresh(db_product)

    # Create image records
    for url in product_in.images:
        img = ProductImage(product_id=db_product.id, url=url)
        session.add(img)
    session.commit()
    session.refresh(db_product)

    return db_product


@router.get("/{product_id}", response_model=ProductRead, dependencies=[Depends(CurrentUser)])
def read_product(
    *,
    session: SessionDep,
    product_id: UUID,
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=ProductRead, dependencies=[Depends(CurrentUser)])
def update_product(
    *,
    session: SessionDep,
    product_id: UUID,
    product_up: ProductUpdate,
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Unique barcode check
    if product_up.barcode and product_up.barcode != product.barcode:
        exists = session.exec(
            select(Product)
            .where(Product.barcode == product_up.barcode)
            .where(Product.id != product_id)
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="Barcode already in use")

    update_data = product_up.model_dump(exclude_unset=True)
    product.sqlmodel_update(update_data)

    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(CurrentUser)])
def delete_product(
    *,
    session: SessionDep,
    product_id: UUID,
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    session.delete(product)
    session.commit()
    return product
