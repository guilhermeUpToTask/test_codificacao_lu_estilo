import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import status
from sqlmodel import Session

from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.client import Client, ClientCreate
from app.models.product import Product, ProductCreate, ProductImage
from app.models.order import Order, OrderItem

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

def create_test_client(session: Session, name="Alice", email=None, cpf=None) -> Client:
    email = email or f"{uuid.uuid4()}@example.com"
    cpf = cpf or str(uuid.uuid4())
    c = ClientCreate(name=name, email=email, cpf=cpf)
    db_client = Client.model_validate(c)
    session.add(db_client)
    session.commit()
    session.refresh(db_client)
    return db_client

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
def test_list_orders_empty(client, db_session):
    user = create_user(db_session)
    r = client.get("/orders/", headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == []

def test_create_order_success(client, db_session):
    user = create_user(db_session)
    client_obj = create_test_client(db_session)
    prod = create_test_product(db_session)
    old_stock = prod.initial_stock
    
    order_payload = {
        "client_id": str(client_obj.id),
        "items": [
            {"product_id": str(prod.id), "quantity": 2, "unit_price": prod.sale_price, "section": prod.section}
        ]
    }
    r = client.post("/orders/", json=order_payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    assert data["client_id"] == str(client_obj.id)
    assert len(data["items"]) == 1

    updated_prod = db_session.get(Product, prod.id)
    assert updated_prod.initial_stock == old_stock - 2

def test_create_order_product_not_found(client, db_session):
    user = create_user(db_session)
    client_obj = create_test_client(db_session)
    fake_id = uuid.uuid4()
    payload = {"client_id": str(client_obj.id), "items": [{"product_id": str(fake_id), "quantity": 1, "unit_price": 1.0, "section": "A1"}]}
    r = client.post("/orders/", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert f"Product {fake_id} not found" in r.json()["detail"]

def test_create_order_insufficient_stock(client, db_session):
    user = create_user(db_session)
    client_obj = create_test_client(db_session)
    prod = create_test_product(db_session)
    payload = {"client_id": str(client_obj.id), "items": [{"product_id": str(prod.id), "quantity": prod.initial_stock + 1, "unit_price": prod.sale_price, "section": prod.section}]}
    r = client.post("/orders/", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert f"Insufficient stock for product {prod.id}" in r.json()["detail"]

def test_read_order_success(client, db_session):
    user = create_user(db_session)
    client_obj = create_test_client(db_session)
    prod = create_test_product(db_session)
    # create via API
    payload = {"client_id": str(client_obj.id), "items": [{"product_id": str(prod.id), "quantity": 1, "unit_price": prod.sale_price, "section": prod.section}]}
    create_resp = client.post("/orders/", json=payload, headers=auth_headers(user))
    order_id = create_resp.json()["id"]
    r = client.get(f"/orders/{order_id}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK

def test_read_order_not_found(client, db_session):
    user = create_user(db_session)
    fake = uuid.uuid4()
    r = client.get(f"/orders/{fake}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json()["detail"] == "Order not found"

def test_update_order_success(client, db_session):
    user = create_user(db_session)
    client_obj = create_test_client(db_session)
    prod = create_test_product(db_session)
    payload = {"client_id": str(client_obj.id), "items": [{"product_id": str(prod.id), "quantity": 1, "unit_price": prod.sale_price, "section": prod.section}]}
    create_resp = client.post("/orders/", json=payload, headers=auth_headers(user))
    order_id = create_resp.json()["id"]

    update_payload = {"status": "shipped"}
    r = client.put(f"/orders/{order_id}", json=update_payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["status"] == "shipped"

def test_update_order_not_found(client, db_session):
    user = create_user(db_session)
    fake = uuid.uuid4()
    r = client.put(f"/orders/{fake}", json={"status": "late"}, headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json()["detail"] == "Order not found"

def test_delete_order_success(client, db_session):
    user = create_user(db_session)
    client_obj = create_test_client(db_session)
    prod = create_test_product(db_session)
    payload = {"client_id": str(client_obj.id), "items": [{"product_id": str(prod.id), "quantity": 1, "unit_price": prod.sale_price, "section": prod.section}]}
    create_resp = client.post("/orders/", json=payload, headers=auth_headers(user))
    order_id = create_resp.json()["id"]

    r = client.delete(f"/orders/{order_id}", headers=auth_headers(user))
    
    assert r.status_code == status.HTTP_204_NO_CONTENT
    assert db_session.get(Order, uuid.UUID(order_id)) is None

def test_delete_order_not_found(client, db_session):
    user = create_user(db_session)
    fake = uuid.uuid4()
    r = client.delete(f"/orders/{fake}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json()["detail"] == "Order not found"
