import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from app.core import user_crud
from app.api.deps import (
    CurrentUser, SessionDep
)

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.user import(
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserRegister,
    UserPublic,
    UsersPublic,
    UserUpdateMe
)

router = APIRouter(prefix="/users", tags=["users"])


router.get("/", response_model=UsersPublic)
def read_users(session:SessionDep, skip: int = 0, limit:int = 100) -> Any:
    """
    Retrive Users.
    """
    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()
    
    statement = select(User).offset(skip).limit(limit)
    users = session.exec(statement).all()
    
    return UsersPublic(data=users, count=count)

@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session:SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """ 
    Update own user.
    """
    
    if user_in.email:
        existing_user = user_crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user

@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session:SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own Password
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="password updated sucessfully")

@router.get("/me", response_model=UserPublic)
def read_user_me(current_user:CurrentUser):
    """
    Get current user
    """
    return current_user

@router.delete("/me", response_model= Message)
def delete_user_me(session:SessionDep, current_user:CurrentUser) -> Any:
    """
    Delete own user.
    """
    session.delete(current_user)
    session.commit()
    return Message(message="user deleted successfully")


#Should not return the user uuid
@router.post("/sign_up", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user
    """
    user = user_crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system"
        )
    user_create = UserCreate.model_validate(user_in)
    user = user_crud.create_user(session=session, user_create=user_create)
    return user

@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep
)-> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User Not Found")
    return user