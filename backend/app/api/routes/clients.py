from fastapi import APIRouter, Body, HTTPException, Query, Depends
from sqlmodel import select
from uuid import UUID
from typing import List, Optional
from app.api.deps import SessionDep, get_current_user
from app.models.client import Client, ClientCreate, ClientRead, ClientUpdate

router = APIRouter(
    prefix="/clients",
    tags=["Clientes"],
    dependencies=[Depends(get_current_user)],
    responses={
        400: {"description": "Requisição Inválida", "content": {"application/json": {"example": {"detail": "Mensagem de erro"}}}},
        404: {"description": "Não Encontrado",   "content": {"application/json": {"example": {"detail": "Cliente não encontrado"}}}}
    }
)

@router.get(
    "/",
    response_model=List[ClientRead],
    summary="Listar Clientes",
    description=(
        "Retorna uma lista paginada de clientes. "
        "Permite filtrar por nome ou e-mail através de parâmetros de consulta."
    ),
)
def list_clients(
    session: SessionDep,
    skip: int = Query(0, ge=0, description="Quantidade de registros a pular"),
    limit: int = Query(10, gt=0, le=100, description="Número máximo de registros retornados"),
    name: Optional[str] = Query(None, description="Filtrar por nome do cliente (busca parcial)"),
    email: Optional[str] = Query(None, description="Filtrar por e-mail do cliente (busca parcial)")
) -> List[ClientRead]:
    """
    Regras de Negócio:
    - Paginação usando `skip` e `limit`.
    - Filtro case-insensitive para `name` e `email`.

    Casos de Uso:
    - Página de administração listando clientes com busca.

    ### Exemplo de Requisição
    ```http
    GET /clients?skip=0&limit=5&name=Acme HTTP/1.1
    Authorization: Bearer <token>
    ```

    ### Exemplo de Resposta
    ```json
    [
      {"id": "uuid1", "name": "Acme Corp", "email": "contato@acme.com", "cpf": "123"},
      {"id": "uuid2", "name": "Acme Ltd", "email": "info@acme.com", "cpf": "456"}
    ]
    ```
    """    
    query = select(Client)

    if name:
        query = query.where(Client.name.ilike(f"%{name}%"))

    if email:
        query = query.where(Client.email.ilike(f"%{email}%"))

    clients = session.exec(query.offset(skip).limit(limit)).all()
    return clients


@router.post(
    "/",
    response_model=ClientRead,
    summary="Criar Cliente",
    description=(
        "Registra um novo cliente no sistema. "
        "Valida unicidade de `email` e `cpf`."
    ),
)
def create_client(
    session: SessionDep,
    client: ClientCreate = Body(
        ...,
        examples={
            "padrao": {
                "summary": "Novo cliente",
                "value": {"name": "João Silva", "email": "joao@exemplo.com", "cpf": "12345678900"}
            }
    })
    ) -> ClientRead:
    """
    Regras de Negócio:
    - `email` e `cpf` devem ser únicos.
    - Retorna HTTP 400 em caso de duplicidade.

    ### Exemplo de Requisição
    ```json
    {"name": "João Silva", "email": "joao@exemplo.com", "cpf": "12345678900"}
    ```

    ### Exemplo de Resposta
    ```json
    {"id": "uuid3", "name": "João Silva", "email": "joao@exemplo.com", "cpf": "12345678900"}
    ```
    """
    email_exists = session.exec(select(Client).where(Client.email == client.email)).first()
    if email_exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    cpf_exists = session.exec(select(Client).where(Client.cpf == client.cpf)).first()
    if cpf_exists:
        raise HTTPException(status_code=400, detail="CPF already registered")

    db_client = Client.model_validate(client)
    session.add(db_client)
    session.commit()
    session.refresh(db_client)
    return db_client


@router.get(
    "/{client_id}",
    response_model=ClientRead,
    summary="Obter Cliente por ID",
    description="Recupera um cliente pelo seu UUID."
)
def read_client(
    session: SessionDep,
    client_id: UUID,
) -> ClientRead:
    """
    Regras de Negócio:
    - Retorna HTTP 404 se o cliente não existir.

    ### Exemplo de Requisição
    ```http
    GET /clients/uuid3 HTTP/1.1
    Authorization: Bearer <token>
    ```

    ### Exemplo de Resposta
    ```json
    {"id": "uuid3", "name": "João Silva", "email": "joao@exemplo.com", "cpf": "12345678900"}
    ```
    """
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.put(
    "/{client_id}",
    response_model=ClientRead,
    summary="Atualizar Cliente",
    description=(
        "Atualiza informações de um cliente existente. "
        "Valida unicidade de `email` e `cpf` atualizados."
    ),
)
def update_client(
    session: SessionDep,
    client_id: UUID,
    client_update: ClientUpdate = Body(
        ..., examples={
            "padrao": {
                "summary": "Atualizar e-mail",
                "value": {"email": "novo@exemplo.com"}
            }
        })
    ) -> ClientRead:
    """
    Regras de Negócio:
    - Não permite trocar para `email` ou `cpf` já existentes.
    - Atualiza apenas campos fornecidos.

    ### Exemplo de Requisição
    ```json
    {"email": "novo@exemplo.com"}
    ```

    ### Exemplo de Resposta
    ```json
    {"id": "uuid3", "name": "João Silva", "email": "novo@exemplo.com", "cpf": "12345678900"}
    ```
    """
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client_update.email and client_update.email != client.email:
        if session.exec(select(Client).where(Client.email == client_update.email)).first():
            raise HTTPException(status_code=400, detail="Email already registered")
    if client_update.cpf and client_update.cpf != client.cpf:
        if session.exec(select(Client).where(Client.cpf == client_update.cpf)).first():
            raise HTTPException(status_code=400, detail="CPF already registered")

    updated_data = client_update.model_dump(exclude_unset=True)
    client.sqlmodel_update(updated_data)
    session.add(client)
    session.commit()
    session.refresh(client)
    return client

@router.delete(
    "/{client_id}",
    summary="Excluir Cliente",
    description="Remove um cliente pelo seu UUID.",
    responses={
        200: {"description": "Exclusão bem-sucedida", "content": {"application/json": {"example": {"ok": True}}}}
    }
)
def delete_client(
    session: SessionDep,
    client_id: UUID
) -> dict:
    """
    Regras de Negócio:
    - Retorna HTTP 404 se o cliente não existir.

    ### Exemplo de Requisição
    ```http
    DELETE /clients/uuid3 HTTP/1.1
    Authorization: Bearer <token>
    ```

    ### Exemplo de Resposta
    ```json
    {"ok": true}
    ```
    """
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    session.delete(client)
    session.commit()
    return {"ok": True}
