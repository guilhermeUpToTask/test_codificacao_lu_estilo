import uuid
from datetime import timedelta

import pytest
from fastapi import status
from sqlmodel import Session, select

from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.client import Client, ClientCreate, ClientRead

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

# Tests

def test_list_clients_empty(client, db_session):
    user = create_user(db_session)
    r = client.get("/clients/", headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == []

def test_create_client_success(client, db_session):
    user = create_user(db_session)
    payload = {"name": "Bob", "email": "bob@example.com", "cpf": "12345678901"}
    r = client.post("/clients/", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["name"] == "Bob"
    assert data["email"] == "bob@example.com"
    assert data["cpf"] == "12345678901"
    assert "id" in data

    # persisted
    from app.models.client import Client as DBClient
    db_c = db_session.get(DBClient, uuid.UUID(data["id"]))
    assert db_c is not None

def test_create_client_duplicate_email(client, db_session):
    user = create_user(db_session)
    existing = create_test_client(db_session, email="same@example.com")
    payload = {"name": "X", "email": existing.email, "cpf": "newcpf"}
    r = client.post("/clients/", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["detail"] == "Email already registered"

def test_create_client_duplicate_cpf(client, db_session):
    user = create_user(db_session)
    existing = create_test_client(db_session, cpf="cpf123")
    payload = {"name": "X", "email": "new@example.com", "cpf": existing.cpf}
    r = client.post("/clients/", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["detail"] == "CPF already registered"

def test_read_client_success(client, db_session):
    user = create_user(db_session)
    c = create_test_client(db_session)
    r = client.get(f"/clients/{c.id}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["id"] == str(c.id)
    assert data["email"] == c.email

def test_read_client_not_found(client, db_session):
    user = create_user(db_session)
    fake_id = uuid.uuid4()
    r = client.get(f"/clients/{fake_id}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json()["detail"] == "Client not found"

def test_update_client_success(client, db_session):
    user = create_user(db_session)
    c = create_test_client(db_session)
    payload = {"name": "Charlie", "email": "charlie@example.com"}
    r = client.put(f"/clients/{c.id}", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["name"] == "Charlie"
    assert data["email"] == "charlie@example.com"

def test_update_client_not_found(client, db_session):
    user = create_user(db_session)
    fake_id = uuid.uuid4()
    payload = {"name": "Nobody"}
    r = client.put(f"/clients/{fake_id}", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json()["detail"] == "Client not found"

def test_update_client_duplicate_email(client, db_session):
    user = create_user(db_session)
    c1 = create_test_client(db_session, email="one@example.com")
    c2 = create_test_client(db_session, email="two@example.com")
    payload = {"email": c2.email}
    r = client.put(f"/clients/{c1.id}", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["detail"] == "Email already registered"

def test_update_client_duplicate_cpf(client, db_session):
    user = create_user(db_session)
    c1 = create_test_client(db_session, cpf="cpfA")
    c2 = create_test_client(db_session, cpf="cpfB")
    payload = {"cpf": c2.cpf}
    r = client.put(f"/clients/{c1.id}", json=payload, headers=auth_headers(user))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.json()["detail"] == "CPF already registered"

def test_delete_client_success(client, db_session):
    user = create_user(db_session)
    c = create_test_client(db_session)
    r = client.delete(f"/clients/{c.id}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == {"ok": True}
    assert db_session.get(Client, c.id) is None

def test_delete_client_not_found(client, db_session):
    user = create_user(db_session)
    fake_id = uuid.uuid4()
    r = client.delete(f"/clients/{fake_id}", headers=auth_headers(user))
    assert r.status_code == status.HTTP_404_NOT_FOUND
    assert r.json()["detail"] == "Client not found"

def test_list_clients_filters(client, db_session):
    user = create_user(db_session)
    create_test_client(db_session, name="Ann", email="ann@example.com")
    create_test_client(db_session, name="Bill", email="bill@example.com")
    # filter by name
    r1 = client.get("/clients/?name=ann", headers=auth_headers(user))
    assert r1.status_code == status.HTTP_200_OK
    assert len(r1.json()) == 1
    # filter by email
    r2 = client.get("/clients/?email=bill@example.com", headers=auth_headers(user))
    assert r2.status_code == status.HTTP_200_OK
    assert len(r2.json()) == 1
