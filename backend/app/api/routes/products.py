from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from uuid import UUID
from sqlmodel import delete, select

from app.api.deps import SessionDep, get_current_user
from app.models.product import (
    Product,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ProductImage,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/", response_model=List[ProductRead], dependencies=[Depends(get_current_user)])
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

    result = session.exec(query.offset(skip).limit(limit)).all()
    products = []
    
    for product in result:
        data = product.model_dump(exclude={"images"})
        data["images"] = [img.url for img in product.images]
        products.append(data)
        
    return products


@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
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
    
    # Create product without images
    data = product_in.model_dump(exclude={"images"})
    db_product = Product(**data)
    
    session.add(db_product)
    session.commit()
    session.refresh(db_product)

    # Create image records
    for url in product_in.images:
        img = ProductImage(product_id=db_product.id, url=url)
        session.add(img)
        
    session.commit()
    session.refresh(db_product)

    result = db_product.model_dump()
    result["images"] = [img.url for img in db_product.images]
    return result


@router.get("/{product_id}", response_model=ProductRead, dependencies=[Depends(get_current_user)])
def read_product(
    *,
    session: SessionDep,
    product_id: UUID,
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    data = product.model_dump(exclude={"images"})
    data["images"] = [img.url for img in product.images]

    return ProductRead(**data)



@router.put("/{product_id}", response_model=ProductRead, dependencies=[Depends(get_current_user)])
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
    
    result = product.model_dump()
    result["images"] = [img.url for img in product.images]
    return result


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_user)])
def delete_product(
    *,
    session: SessionDep,
    product_id: UUID,
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # delete all image rows first
    session.exec(delete(ProductImage).where(ProductImage.product_id == product.id))
    session.delete(product)
    session.commit()
    
    return None
