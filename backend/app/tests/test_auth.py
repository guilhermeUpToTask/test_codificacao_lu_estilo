import uuid
from datetime import timedelta

import pytest
from fastapi import status
from sqlmodel import Session

from app.core import security, user_crud
from app.models.user import (
    User,
    UserRole,
)


def create_test_user(db_session: Session) -> User:
    """
    Helper: insert a user directly into the test DB.
    """
    user = User(
        email="test@example.com",
        hashed_password=security.get_password_hash("testpassword"),
        is_active=True,
        full_name="Test User",
        role=UserRole.CLIENT,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_register_user(client, db_session):
    payload = {
        "email": "newuser@example.com",
        "password": "newpassword",
        "full_name": "New User"
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    
    # returns UserPublic: id, email, is_active, full_name, role
    assert uuid.UUID(data["id"])
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert data["role"] == UserRole.CLIENT.value

    # verify persisted
    from app.models.user import User as DBUser
    db_user = db_session.get(DBUser, uuid.UUID(data["id"]))
    assert db_user is not None
    assert db_user.email == payload["email"]


def test_register_existing_user(client, db_session):
    # pre-create
    create_test_user(db_session)

    payload = {
        "email": "test@example.com",
        "password": "testpassword",
        "full_name": "Test User"
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "The user with this email already exists in the system"


def test_login_success(client, db_session):
    create_test_user(db_session)

    form_data = {
        "username": "test@example.com",
        "password": "testpassword",
    }
    response = client.post("/auth/login", data=form_data)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, db_session):
    create_test_user(db_session)

    form_data = {
        "username": "test@example.com",
        "password": "wrongpassword",
    }
    response = client.post("/auth/login", data=form_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_nonexistent_user(client):
    form_data = {
        "username": "noone@example.com",
        "password": "whatever",
    }
    response = client.post("/auth/login", data=form_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Incorrect email or password"


def test_test_token_valid(client, db_session):
    user = create_test_user(db_session)

    token = security.create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=15)
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/auth/login/test-token", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    print(f"data: {data}")
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["role"] == user.role.value


def test_test_token_invalid(client):
    headers = {"Authorization": "Bearer invalid.token.here"}
    response = client.post("/auth/login/test-token", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Could not validate credentials"
