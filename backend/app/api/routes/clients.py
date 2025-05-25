from fastapi import APIRouter, HTTPException, Query, Depends
from sqlmodel import select
from uuid import UUID
from typing import List, Optional
from app.api.deps import SessionDep, get_current_user
from app.models.client import Client, ClientCreate, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("/", response_model=List[ClientRead], dependencies=[Depends(get_current_user)])
def list_clients(
    *,
    session: SessionDep,
    skip: int = 0,
    limit: int = 10,
    name: Optional[str] = Query(None),
    email: Optional[str] = Query(None)
):
    query = select(Client)

    if name:
        query = query.where(Client.name.ilike(f"%{name}%"))

    if email:
        query = query.where(Client.email.ilike(f"%{email}%"))

    clients = session.exec(query.offset(skip).limit(limit)).all()
    return clients


@router.post("/", response_model=ClientRead, dependencies=[Depends(get_current_user)])
def create_client(session: SessionDep, client: ClientCreate):
    
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


@router.get("/{client_id}", response_model=ClientRead, dependencies=[Depends(get_current_user)])
def read_client(session: SessionDep, client_id: UUID):
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientRead, dependencies=[Depends(get_current_user)])
def update_client(
    session: SessionDep, client_id: UUID, client_update: ClientUpdate
):
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if client_update.email and client_update.email != client.email:
        email_exists = session.exec(select(Client).where(Client.email == client_update.email)).first()
        if email_exists:
            raise HTTPException(status_code=400, detail="Email already registered")

    if client_update.cpf and client_update.cpf != client.cpf:
        cpf_exists = session.exec(select(Client).where(Client.cpf == client_update.cpf)).first()
        if cpf_exists:
            raise HTTPException(status_code=400, detail="CPF already registered")

    client_data = client_update.model_dump(exclude_unset=True)
    client_update.sqlmodel_update(client_data)
    session.add(client_update)
    session.commit()
    session.refresh(client)
    return client


@router.delete("/{client_id}", dependencies=[Depends(get_current_user)])
def delete_client(session: SessionDep, client_id: UUID):
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    session.delete(client)
    session.commit()
    return {"ok": True}
