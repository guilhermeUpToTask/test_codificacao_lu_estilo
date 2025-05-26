from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID
from sqlmodel import delete, select
from app.api.deps import SessionDep, get_current_user
from app.models.order import (
    Order,
    OrderCreate,
    OrderRead,
    OrderUpdate,
    OrderItem,
)
from app.models.product import Product

router = APIRouter(
    prefix="/orders",
    tags=["Pedidos"],
    dependencies=[Depends(get_current_user)],
    responses={
        401: {"description": "Não autorizado - token inválido ou inexistente"},
        403: {"description": "Acesso proibido"}
    }
)

@router.get(
    "/",
    response_model=List[OrderRead],
    summary="Listar pedidos",
    description="""
Retorna uma lista de pedidos filtrados de acordo com parâmetros opcionais.

Regras de negócio:
- Se não houver filtros, retorna todos os pedidos paginados.
- Filtros por data consideram inclusive o início e fim do dia.
- Filtro por seção retorna apenas pedidos contendo itens na seção especificada.

Casos de uso:
- Administradores verificam histórico de vendas.
- Clientes acompanham seus pedidos.
""",
    responses={
        200: {
            "description": "Lista de pedidos retornada com sucesso",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "client_id": "1c9d4f1a-3b69-4c9b-8f8b-1234567890ab",
                            "order_date": "2025-05-20T14:30:00",
                            "status": "PENDING",
                            "items": [
                                {
                                    "product_id": "5b1a6a1f-2b3c-4d5e-9f0a-abcdef123456",
                                    "quantity": 2,
                                    "unit_price": 49.90,
                                    "section": "eletrônicos"
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }
)
def list_orders(
    *,
    session: SessionDep,
    start_date: Optional[date] = Query(None, description="Início do período de pedidos (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fim do período de pedidos (YYYY-MM-DD)"),
    section: Optional[str] = Query(None, description="Filtrar por seção do produto"),
    order_id: Optional[UUID] = Query(None, description="Filtrar por ID do pedido"),
    status: Optional[str] = Query(None, description="Filtrar por status do pedido"),
    client_id: Optional[UUID] = Query(None, description="Filtrar por ID do cliente"),
    skip: int = Query(0, ge=0, description="Quantidade de registros a pular para paginação"),
    limit: int = Query(10, ge=1, description="Quantidade máxima de registros a retornar"),
):
    query = select(Order)
    if start_date:
        query = query.where(Order.order_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(Order.order_date <= datetime.combine(end_date, datetime.max.time()))
    if order_id:
        query = query.where(Order.id == order_id)
    if status:
        query = query.where(Order.status == status)
    if client_id:
        query = query.where(Order.client_id == client_id)
    if section:
        query = query.join(Order.items).where(OrderItem.section == section)

    orders: List[Order] = session.exec(query.offset(skip).limit(limit)).all()
    result: List[OrderRead] = []
    for o in orders:
        data = o.model_dump(exclude={"items"})
        items = [OrderItem.model_validate(i) for i in o.items]
        data["items"] = [i.model_dump() for i in items]
        result.append(OrderRead(**data))
    return result


@router.post(
    "/",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo pedido",
    description="""
Cria um novo pedido após validar disponibilidade de estoque.

Regras de negócio:
- Verifica se cada produto existe; caso não, retorna 404.
- Verifica estoque mínimo; se insuficiente, retorna 400.
- Deduz quantidade do estoque e cria itens associados ao pedido.
""",
)
def create_order(
    *,
    session: SessionDep,
    order_in: OrderCreate = Body(..., 
        examples={
            "pedido_valido": {
                "summary": "Exemplo de pedido válido",
                "value": {
                    "client_id": "1c9d4f1a-3b69-4c9b-8f8b-1234567890ab",
                    "items": [
                        {"product_id": "5b1a6a1f-2b3c-4d5e-9f0a-abcdef123456", "quantity": 2, "unit_price": 49.90, "section": "eletrônicos"}
                    ]
                }
            }
        }
    ),
):
    for item in order_in.items:
        product = session.get(Product, item.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.initial_stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {item.product_id}",
            )

    db_order = Order(client_id=order_in.client_id)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)

    for item in order_in.items:
        product = session.get(Product, item.product_id)
        product.initial_stock -= item.quantity
        session.add(product)
        order_item = OrderItem(
            order_id=db_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            section=item.section,
        )
        session.add(order_item)
    session.commit()
    session.refresh(db_order)

    data = db_order.model_dump(exclude={"items"})
    data["items"] = [item.model_dump() for item in db_order.items]
    return OrderRead(**data)


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    summary="Obter um pedido",
    description="""
Retorna os detalhes de um pedido específico pelo seu ID.

Casos de uso:
- Visualização de status e histórico de um pedido.
""",
    responses={
        404: {"description": "Order not found"}
    }
)
def read_order(
    *,
    session: SessionDep,
    order_id: UUID,
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    data = order.model_dump(exclude={"items"})
    data["items"] = [item.model_dump() for item in order.items]
    return OrderRead(**data)


@router.put(
    "/{order_id}",
    response_model=OrderRead,
    summary="Atualizar status de pedido",
    description="""
Atualiza o status de um pedido existente.

Regras de negócio:
- Apenas o campo `status` pode ser alterado via este endpoint.
- Registra timestamp de atualização.
""",
    responses={
        404: {"description": "Order not found"}
    }
)
def update_order(
    *,
    session: SessionDep,
    order_id: UUID,
    order_up: OrderUpdate = Body(...,
        examples={
            "exemplo_atualizacao": {
                "summary": "Atualização de status para ENTREGUE",
                "value": {"status": "DELIVERED"}
            }
        }
    ),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order_up.status:
        order.status = order_up.status
    order.updated_at = datetime.utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    data = order.model_dump(exclude={"items"})
    data["items"] = [item.model_dump() for item in order.items]
    return OrderRead(**data)


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir pedido",
    description="""
Remove um pedido e seus itens do sistema.

Casos de uso:
- Cancelamento definitivo de pedidos não entregues.
""",
    responses={
        404: {"description": "Pedido não encontrado"},
        204: {"description": "Pedido excluído com sucesso"}
    }
)
def delete_order(
    *,
    session: SessionDep,
    order_id: UUID,
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    session.exec(delete(OrderItem).where(OrderItem.order_id == order_id))
    session.delete(order)
    session.commit()
    return None
