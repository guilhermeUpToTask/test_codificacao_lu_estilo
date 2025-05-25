import uuid
from datetime import timedelta

import pytest
from fastapi import status
from sqlmodel import Session

from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole, UpdatePassword

# Helpers

def create_user(session: Session, email: str, password: str, role: UserRole = UserRole.CLIENT) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name="Test User",
        is_active=True,
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=60))
    return {"Authorization": f"Bearer {token}"}


# Tests

def test_read_user_me(client, db_session):
    user = create_user(db_session, "alice@example.com", "secret123")
    response = client.get("/users/me", headers=auth_headers(user))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == user.email
    assert data["id"] == str(user.id)


def test_update_user_me_success(client, db_session):
    user = create_user(db_session, "bob@example.com", "secret123")
    payload = {"full_name": "Bobby", "email": "bob.new@example.com"}
    response = client.patch("/users/me", json=payload, headers=auth_headers(user))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["full_name"] == "Bobby"
    assert data["email"] == "bob.new@example.com"

    # verify persisted
    db_user = db_session.get(User, user.id)
    assert db_user.email == "bob.new@example.com"


def test_update_user_me_conflict(client, db_session):
    user1 = create_user(db_session, "c1@example.com", "secret123")
    user2 = create_user(db_session, "c2@example.com", "secret123")
    # user1 attempts to take user2's email
    payload = {"email": "c2@example.com"}
    response = client.patch("/users/me", json=payload, headers=auth_headers(user1))
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "User with this email already exists"


def test_update_password_me_success(client, db_session):
    user = create_user(db_session, "dave@example.com", "oldpass123")
    old_hash = user.hashed_password  # ← capture old
    payload = {"current_password": "oldpass123", "new_password": "newpass456"}
    response = client.patch("/users/me/password", json=payload, headers=auth_headers(user))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "password updated sucessfully"

    # ensure password actually changed
    updated = db_session.get(User, user.id)
    assert updated.hashed_password != old_hash


def test_update_password_me_wrong_current(client, db_session):
    user = create_user(db_session, "eve@example.com", "pass1234")
    payload = {"current_password": "wrong1234", "new_password": "newpass123"}
    response = client.patch("/users/me/password", json=payload, headers=auth_headers(user))
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Incorrect password"


def test_update_password_me_same_password(client, db_session):
    user = create_user(db_session, "frank@example.com", "samepass")
    payload = {"current_password": "samepass", "new_password": "samepass"}
    response = client.patch("/users/me/password", json=payload, headers=auth_headers(user))
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "New password cannot be the same as the current one"


def test_delete_user_me(client, db_session):
    user = create_user(db_session, "gary@example.com", "pw123456")
    response = client.delete("/users/me", headers=auth_headers(user))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "user deleted successfully"
    # Should no longer exist
    assert db_session.get(User, user.id) is None


def test_read_all_users_admin(client, db_session):
    # create a few users
    create_user(db_session, "u1@example.com", "pw1")
    create_user(db_session, "u2@example.com", "pw2")
    admin = create_user(db_session, "admin@example.com", "adminpw", role=UserRole.ADMIN)

    response = client.get("/users", headers=auth_headers(admin))
    assert response.status_code == status.HTTP_200_OK
    
    payload = response.json()
    assert "data" in payload and "count" in payload
    assert isinstance(payload["data"], list)
    assert payload["count"] >= 3


def test_read_all_users_non_admin(client, db_session):
    user = create_user(db_session, "henry@example.com", "pw")
    response = client.get("/users", headers=auth_headers(user))
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_read_user_by_id_as_self(client, db_session):
    user = create_user(db_session, "ivy@example.com", "pw")
    response = client.get(f"/users/{user.id}", headers=auth_headers(user))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == user.email


def test_read_user_by_id_non_admin(client, db_session):
    user = create_user(db_session, "jack@example.com", "pw")
    other = create_user(db_session, "kate@example.com", "pw")
    response = client.get(f"/users/{other.id}", headers=auth_headers(user))
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_read_user_by_id_admin(client, db_session):
    other = create_user(db_session, "leo@example.com", "pw")
    admin = create_user(db_session, "admin2@example.com", "pw", role=UserRole.ADMIN)
    response = client.get(f"/users/{other.id}", headers=auth_headers(admin))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == other.email


def test_update_user_admin_success(client, db_session):
    target = create_user(db_session, "mark@example.com", "pw")
    admin = create_user(db_session, "admin3@example.com", "pw", role=UserRole.ADMIN)
    payload = {"full_name": "Mark Twain", "email": "mark.new@example.com"}
    response = client.patch(f"/users/{target.id}", json=payload, headers=auth_headers(admin))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["full_name"] == "Mark Twain"
    assert data["email"] == "mark.new@example.com"


def test_update_user_admin_not_found(client, db_session):
    admin = create_user(db_session, "admin4@example.com", "pw", role=UserRole.ADMIN)
    fake_id = uuid.uuid4()
    payload = {"full_name": "No One"}
    response = client.patch(f"/users/{fake_id}", json=payload, headers=auth_headers(admin))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_user_admin_email_conflict(client, db_session):
    target = create_user(db_session, "oscar@example.com", "pw")
    other = create_user(db_session, "peter@example.com", "pw")
    admin = create_user(db_session, "admin5@example.com", "pw", role=UserRole.ADMIN)
    payload = {"email": "peter@example.com"}
    response = client.patch(f"/users/{target.id}", json=payload, headers=auth_headers(admin))
    assert response.status_code == status.HTTP_409_CONFLICT


def test_delete_user_admin_success(client, db_session):
    target = create_user(db_session, "quinn@example.com", "pw")
    admin = create_user(db_session, "admin6@example.com", "pw", role=UserRole.ADMIN)
    response = client.delete(f"/users/{target.id}", headers=auth_headers(admin))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "User deleted successfully"
    assert db_session.get(User, target.id) is None


def test_delete_user_admin_not_found(client, db_session):
    admin = create_user(db_session, "admin7@example.com", "pw", role=UserRole.ADMIN)
    fake_id = uuid.uuid4()
    response = client.delete(f"/users/{fake_id}", headers=auth_headers(admin))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_user_admin_self_forbidden(client, db_session):
    admin = create_user(db_session, "admin8@example.com", "pw", role=UserRole.ADMIN)
    response = client.delete(f"/users/{admin.id}", headers=auth_headers(admin))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Super users are not allowed to delete themselves"
