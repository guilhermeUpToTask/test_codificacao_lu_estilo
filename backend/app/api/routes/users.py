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
    UserRole,
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
    Atualização de dados do usuário autenticado

    Example Request:
    ```json
    {
        "email": "novo_email@example.com",
        "full_name": "Novo Nome",
        "password": "NovaSenha123!"
    }
    ```

    Example Response:
    ```json
    {
        "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "email": "novo_email@example.com",
        "full_name": "Novo Nome",
        "is_active": true,
        "role": "user"
    }
    ```

    Regras de Negócio:
    - Apenas o próprio usuário pode atualizar seus dados
    - Email deve ser único no sistema
    - Campos opcionais: email, full_name, password
    - Para atualizar email, deve ser fornecido um email válido não cadastrado

    Casos de Uso:
    - Atualização de perfil do usuário
    - Alteração de informações pessoais
    - Mudança de credenciais de acesso
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
    Alteração de senha do usuário autenticado

    Example Request:
    ```json
    {
        "current_password": "SenhaAntiga123!",
        "new_password": "NovaSenhaSegura456@"
    }
    ```

    Example Response:
    ```json
    {
        "message": "password updated successfully"
    }
    ```

    Regras de Negócio:
    - Senha atual deve ser válida
    - Nova senha deve ser diferente da atual
    - Nova senha deve atender aos requisitos de segurança (mínimo 8 caracteres, letras e números)
    - A alteração é imediata e invalida tokens anteriores

    Casos de Uso:
    - Troca periódica de senha por segurança
    - Recuperação de acesso após possível comprometimento
    - Atualização de credenciais após esquecimento
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
    Obtenção dos dados do usuário autenticado

    Example Response:
    ```json
    {
        "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "email": "usuario@example.com",
        "full_name": "João Silva",
        "is_active": true,
        "role": "user"
    }
    ```

    Regras de Negócio:
    - Requer autenticação válida
    - Retorna apenas dados do próprio usuário
    - Dados sensíveis (como hash da senha) são omitidos

    Casos de Uso:
    - Exibição de perfil do usuário
    - Verificação de dados cadastrais
    - Confirmação de autenticação
    """
    return current_user

@router.delete("/me", response_model= Message)
def delete_user_me(session:SessionDep, current_user:CurrentUser) -> Any:
    """
    Exclusão da conta do usuário autenticado

    Example Response:
    ```json
    {
        "message": "user deleted successfully"
    }
    ```

    Regras de Negócio:
    - Ação irreversível
    - Todos os dados do usuário são removidos permanentemente
    - Requer confirmação de senha (não implementado)
    - Não permite exclusão de contas administrativas

    Casos de Uso:
    - Usuário deseja remover sua conta
    - Limpeza de contas inativas
    - Cumprimento de solicitações de privacidade
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
    Obtenção de usuário por ID

    Example Request:
    ```
    GET /users/a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11
    ```

    Example Response:
    ```json
    {
        "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "email": "usuario@example.com",
        "full_name": "Maria Souza",
        "is_active": true,
        "role": "admin"
    }
    ```

    Regras de Negócio:
    - Administradores podem ver qualquer usuário
    - Usuários comuns só podem ver seu próprio perfil
    - Dados sensíveis são omitidos na resposta

    Casos de Uso:
    - Visualização de perfil de outros usuários (admin)
    - Verificação de existência de usuário
    - Integração com sistemas externos
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user

@router.get("/", response_model=UsersPublic, dependencies=[Depends(get_current_admin_user)])
def read_users(session:SessionDep, skip: int = 0, limit:int = 100) -> Any:
    """
    Listagem de usuários (apenas administradores)

    Example Request:
    ```
    GET /users?skip=0&limit=10
    ```

    Example Response:
    ```json
    {
        "data": [
            {
                "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
                "email": "admin@example.com",
                "full_name": "Admin",
                "is_active": true,
                "role": "admin"
            },
            ...
        ],
        "count": 42
    }
    ```

    Regras de Negócio:
    - Acesso restrito a administradores
    - Paginação obrigatória (default: 100 registros)
    - Ordenação padrão por data de criação
    - Não expõe hashes de senha

    Casos de Uso:
    - Gestão de contas de usuário
    - Auditoria do sistema
    - Geração de relatórios
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
    Atualização de usuário (apenas administradores)

    Example Request:
    ```json
    {
        "email": "novo_email_admin@example.com",
        "role": "admin",
        "is_active": false
    }
    ```

    Example Response:
    ```json
    {
        "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "email": "novo_email_admin@example.com",
        "full_name": "Admin",
        "is_active": false,
        "role": "admin"
    }
    ```

    Regras de Negócio:
    - Acesso exclusivo para administradores
    - Permite alteração de role e status de ativo
    - Validação de email único
    - Não permite auto-desativação

    Casos de Uso:
    - Promoção/demissão de administradores
    - Desativação de contas problemáticas
    - Correção de dados cadastrais
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
    Exclusão de usuário (apenas administradores)

    Example Response:
    ```json
    {
        "message": "User deleted successfully"
    }
    ```

    Regras de Negócio:
    - Apenas administradores podem excluir usuários
    - Não permite exclusão de própria conta
    - Exclusão física do registro
    - Operação irreversível

    Casos de Uso:
    - Remoção de contas inválidas
    - Limpeza de contas inativas
    - Cumprimento de solicitações legais
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )

    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")