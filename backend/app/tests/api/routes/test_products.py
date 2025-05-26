import uuid
from datetime import date, timedelta

import pytest
from fastapi import status
from sqlmodel import Session, select

from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.product import Product, ProductCreate, ProductImage

# Helpers

def create_user(session: Session, role: UserRole = UserRole.CLIENT) -> User:
    u = User(
        email=f"{uuid.uuid4()}@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Test User",
        is_active=True,
        role=role,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u

def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=60))
    return {"Authorization": f"Bearer {token}"}

def create_test_product(session: Session, **kwargs) -> Product:
    # 1) Build scalar fields only (no images here)
    data = {
        "description": kwargs.get("description", "Test Product"),
        "sale_price": kwargs.get("sale_price", 9.99),
        "barcode": kwargs.get("barcode", str(uuid.uuid4())),
        "section": kwargs.get("section", "A1"),
        "category": kwargs.get("category", "General"),
        "initial_stock": kwargs.get("initial_stock", 5),
        "expiration_date": kwargs.get(
            "expiration_date", date.today() + timedelta(days=30)
        ),
    }
    p = Product(**data)
    session.add(p)
    session.commit()
    session.refresh(p)

    # 2) Add the images exactly as the real endpoint does
    images = kwargs.get("images", [f"https://example.com/{uuid.uuid4()}.jpg"])
    for url in images:
        img = ProductImage(product_id=p.id, url=url)
        session.add(img)
    session.commit()
    session.refresh(p)

    return p

# Tests

def test_list_products_empty(client, db_session):
    user = create_user(db_session)
    r = client.get("/products/", headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == []

def test_create_product_success(client, db_session):
    user = create_user(db_session)
    payload = {
        "description": "Widget",
        "sale_price": 19.99,
        "barcode": "BAR123",
        "section": "Shelf1",
        "category": "Tools",
        "initial_stock": 10,
        "expiration_date": str(date.today() + timedelta(days=90)),
        "images": ["https://img1", "https://img2"]
    }
    r = client.post("/products/", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    assert data["barcode"] == "BAR123"
    assert set(data["images"]) == set(payload["images"])
    assert "id" in data

    db_p = db_session.get(Product, uuid.UUID(data["id"]))
    assert db_p is not None

def test_create_product_duplicate_barcode(client, db_session):
    user = create_user(db_session)
    create_test_product(db_session, barcode="DUPLICATE")
    payload = {
        "description": "X",
        "sale_price": 1.23,
        "barcode": "DUPLICATE",
        "section": "Sec",
        "initial_stock": 1,
        "images": []
    }
    r = client.post("/products/", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["detail"] == "Barcode already in use"

def test_read_product_success(client, db_session):
    user = create_user(db_session)
    p = create_test_product(db_session)
    r = client.get(f"/products/{p.id}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["id"] == str(p.id)
    assert data["description"] == p.description

def test_read_product_not_found(client, db_session):
    user = create_user(db_session)
    fake = uuid.uuid4()
    r = client.get(f"/products/{fake}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json()["detail"] == "Product not found"

def test_update_product_success(client, db_session):
    user = create_user(db_session)
    p = create_test_product(db_session, barcode="UPD1")
    payload = {"description": "New Desc", "barcode": "UPD2"}
    r = client.put(f"/products/{p.id}", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["description"] == "New Desc"
    assert data["barcode"] == "UPD2"

def test_update_product_not_found(client, db_session):
    user = create_user(db_session)
    fake = uuid.uuid4()
    r = client.put(f"/products/{fake}", json={"description": "X"}, headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json()["detail"] == "Product not found"

def test_update_product_duplicate_barcode(client, db_session):
    user = create_user(db_session)
    p1 = create_test_product(db_session, barcode="A1")
    p2 = create_test_product(db_session, barcode="B2")
    r = client.put(f"/products/{p1.id}", json={"barcode": "B2"}, headers=auth_headers(user))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["detail"] == "Barcode already in use"

def test_delete_product_success(client, db_session):
    user = create_user(db_session)
    p = create_test_product(db_session)
    r = client.delete(f"/products/{p.id}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_204_NO_CONTENT
    # verify deletion
    assert db_session.get(Product, p.id) is None

def test_list_products_filters(client, db_session):
    user = create_user(db_session)
    create_test_product(db_session, category="CatA", sale_price=5, initial_stock=2)
    create_test_product(db_session, category="CatB", sale_price=15, initial_stock=0)
    # by category
    r1 = client.get("/products/?category=CatA", headers=auth_headers(user))
    assert r1.status_code == status.HTTP_200_OK
    assert all(p["category"] == "CatA" for p in r1.json())
    # by min_price
    r2 = client.get("/products/?min_price=10", headers=auth_headers(user))
    assert all(p["sale_price"] >= 10 for p in r2.json())
    # by max_price
    r3 = client.get("/products/?max_price=10", headers=auth_headers(user))
    assert all(p["sale_price"] <= 10 for p in r3.json())
    # available True
    r4 = client.get("/products/?available=true", headers=auth_headers(user))
    assert all(p["initial_stock"] > 0 for p in r4.json())
    # available False
    r5 = client.get("/products/?available=false", headers=auth_headers(user))
    assert all(p["initial_stock"] <= 0 for p in r5.json())
