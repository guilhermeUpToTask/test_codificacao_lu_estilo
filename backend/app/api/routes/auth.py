from datetime import timedelta
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.core import user_crud
from app.api.deps import CurrentUser, SessionDep
from app.core import security
from app.core.config import settings
from app.models.user import Token, UserCreate, UserPublic, UserRegister

router = APIRouter(tags=["auth"], prefix="/auth")

@router.post("/login", response_model=Token)
def login_acces_token(
    session:SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
)-> Token:
    """
    Autenticação OAuth2 para obtenção de token de acesso

    Example Request (form data):
    ```
    username: user@example.com
    password: string
    ```

    Example Response:
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer"
    }
    ```

    Regras de Negócio:
    - O email e senha devem corresponder a um usuário cadastrado
    - Usuários inativos não podem obter tokens
    - O token expira após 30 minutos (configurável nas settings)
    
    Casos de Uso:
    - Autenticação de usuários para acesso à API
    - Geração de token JWT para requisições subsequentes
    - Integração com sistemas OAuth2 compatíveis
    """
    user = user_crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Usuário inativo")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )
    
@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Validação de token de acesso

    Example Request Headers:
    ```
    Authorization: Bearer <access_token>
    ```

    Example Response:
    ```json
    {
        "id": 1,
        "email": "user@example.com",
        "full_name": "João Silva",
        "is_active": true
    }
    ```

    Regras de Negócio:
    - O token deve ser válido e não expirado
    - Retorna os dados do usuário associado ao token
    - Apenas usuários ativos podem ter tokens válidos

    Casos de Uso:
    - Verificação da validade do token
    - Obtenção rápida dos dados do usuário autenticado
    - Teste de conexão com a API usando credenciais
    """
    return current_user

@router.post("/register", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Cadastro de novo usuário

    Example Request:
    ```json
    {
        "email": "novo@example.com",
        "password": "SenhaSegura123!",
        "full_name": "Maria Oliveira"
    }
    ```

    Example Response:
    ```json
    {
        "id": 2,
        "email": "novo@example.com",
        "full_name": "Maria Oliveira",
        "is_active": true
    }
    ```

    Regras de Negócio:
    - O email deve ser único no sistema
    - Senha deve ter pelo menos 8 caracteres
    - Usuário é ativado automaticamente após cadastro
    - Campos obrigatórios: email, password, full_name

    Casos de Uso:
    - Registro de novos usuários na plataforma
    - Criação de contas para acesso ao sistema
    - Integração com formulários de cadastro
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