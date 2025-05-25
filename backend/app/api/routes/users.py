import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from app.core import user_crud
from app.api.deps import (
    CurrentUser, SessionDep, get_current_admin_user
)

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.user import(
    Message,
    UpdatePassword,
    User,
    UserPublic,
    UserUpdate,
    UsersPublic,
    UserUpdateMe
)

router = APIRouter(prefix="/users", tags=["users"])

# User routes
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


#Private routes
@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user

router.get("/", response_model=UsersPublic, dependencies=[Depends(get_current_admin_user)])
def read_users(session:SessionDep, skip: int = 0, limit:int = 100) -> Any:
    """
    Retrive Users.
    """
    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()
    
    statement = select(User).offset(skip).limit(limit)
    users = session.exec(statement).all()
    
    return UsersPublic(data=users, count=count)

@router.patch("/{user_id}",dependencies=[Depends(get_current_admin_user)],response_model=UserPublic,)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = user_crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = user_crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_admin_user)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.exec(statement)  # type: ignore
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")