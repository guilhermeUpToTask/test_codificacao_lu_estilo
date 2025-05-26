from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from uuid import UUID
from sqlmodel import delete, select

from app.api.deps import SessionDep, get_current_user
from app.models.product import (
    Product,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ProductImage,
)

router = APIRouter(
    prefix="/products",
    tags=["Products"],
    dependencies=[Depends(get_current_user)],
    responses={
        401: {"description": "Não autorizado - Credenciais inválidas ou ausentes."},
        404: {"description": "Não encontrado - Recurso não existe."},
        400: {"description": "Requisição inválida - Entrada inválida ou violação de regra de negócio."}
    }
)

@router.get(
    "/",
    response_model=List[ProductRead],
    summary="Listar Produtos",
    description=(
        "Recupera uma lista paginada de produtos com filtros opcionais. "
        "É possível filtrar por categoria, faixa de preço e disponibilidade."
    ),
    openapi_extra={
        "x-examples": {
            "Listagem Básica": {
                "summary": "Buscar os primeiros 10 produtos",
                "value": {
                    "skip": 0,
                    "limit": 10
                }
            },
            "Filtrado": {
                "summary": "Buscar eletrônicos disponíveis abaixo de $500",
                "value": {
                    "category": "electronics",
                    "max_price": 500,
                    "available": True
                }
            }
        }
    }
)
def list_products(
    session: SessionDep,
    skip: int = Query(0, ge=0, description="Número de itens a pular (offset)."),
    limit: int = Query(10, ge=1, description="Número máximo de itens a retornar."),
    category: Optional[str] = Query(None, description="Filtrar por categoria de produto."),
    min_price: Optional[float] = Query(None, ge=0, description="Preço mínimo de venda."),
    max_price: Optional[float] = Query(None, ge=0, description="Preço máximo de venda."),
    available: Optional[bool] = Query(
        None,
        description=(
            "Filtrar por disponibilidade de estoque: True retorna produtos em estoque, "
            "False retorna produtos fora de estoque."
        )
    ),
):
    """
    Regras de Negócio:
    - Se `available` for True, retorna apenas produtos com initial_stock > 0.
    - Se `available` for False, retorna apenas produtos com initial_stock <= 0.
    - `min_price` e `max_price` definem um intervalo de preço inclusivo.

    Casos de Uso:
    - Paginar através de todos os produtos.
    - Filtrar produtos durante navegação em catálogo ou relatórios.
    """
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    if min_price is not None:
        query = query.where(Product.sale_price >= min_price)
    if max_price is not None:
        query = query.where(Product.sale_price <= max_price)
    if available is True:
        query = query.where(Product.initial_stock > 0)
    elif available is False:
        query = query.where(Product.initial_stock <= 0)

    result = session.exec(query.offset(skip).limit(limit)).all()
    products = []
    for product in result:
        data = product.model_dump(exclude={"images"})
        data["images"] = [img.url for img in product.images]
        products.append(data)
    return products

@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar Produto",
    description=(
        "Cria um novo produto. O código de barras (barcode) deve ser único. "
        "A criação inicial não inclui registros de imagens; as imagens são adicionadas após a criação."
    ),
    openapi_extra={
        "x-examples": {
            "Criar com Imagens": {
                "summary": "Criar um novo fone de ouvido",
                "value": {
                    "name": "Wireless Headphones",
                    "barcode": "1234567890123",
                    "category": "electronics",
                    "sale_price": 149.99,
                    "initial_stock": 50,
                    "images": [
                        "https://example.com/headphones1.jpg",
                        "https://example.com/headphones2.jpg"
                    ]
                }
            }
        }
    }
)
def create_product(
    session: SessionDep,
    product_in: ProductCreate,
):
    """
    Regras de Negócio:
    - O barcode deve ser único; tentativas de reutilizar um código existente retornam 400.
    - As imagens são armazenadas separadamente após a criação do produto.

    Casos de Uso:
    - Administrador cria novos SKUs no catálogo.
    """
    existing = session.exec(select(Product).where(Product.barcode == product_in.barcode)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Barcode already in use")
    data = product_in.model_dump(exclude={"images"})
    db_product = Product(**data)

    session.add(db_product)
    session.commit()
    session.refresh(db_product)

    for url in product_in.images:
        img = ProductImage(product_id=db_product.id, url=url)
        session.add(img)
    session.commit()
    session.refresh(db_product)

    result = db_product.model_dump()
    result["images"] = [img.url for img in db_product.images]
    return result

@router.get(
    "/{product_id}",
    response_model=ProductRead,
    summary="Obter Produto",
    description="Recupera um único produto pelo seu UUID.",
    openapi_extra={
        "x-examples": {
            "Exemplo de Busca": {
                "summary": "Obter produto por ID",
                "value": {"product_id": "11111111-2222-3333-4444-555555555555"}
            }
        }
    }
)
def read_product(
    session: SessionDep,
    product_id: UUID,
):
    """
    Regras de Negócio:
    - Retorna 404 se o produto não existir.

    Casos de Uso:
    - Exibir detalhes do produto em interfaces administrativas ou de usuário.
    """
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    data = product.model_dump(exclude={"images"})
    data["images"] = [img.url for img in product.images]
    return ProductRead(**data)

@router.put(
    "/{product_id}",
    response_model=ProductRead,
    summary="Atualizar Produto",
    description=(
        "Atualiza campos de um produto existente. "
        "Atualizações de barcode devem permanecer únicas entre os produtos."
    ),
    openapi_extra={
        "x-examples": {
            "Exemplo de Atualização": {
                "summary": "Modificar preço de venda e estoque",
                "value": {
                    "sale_price": 129.99,
                    "initial_stock": 75
                }
            }
        }
    }
)
def update_product(
    session: SessionDep,
    product_id: UUID,
    product_up: ProductUpdate,
):
    """
    Regras de Negócio:
    - Não é possível atualizar para um barcode que já existe em outro produto.
    - Atualizações parciais são permitidas; somente os campos fornecidos são alterados.

    Casos de Uso:
    - Corrigir erros de preço ou ajustar estoque durante auditorias.
    """
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product_up.barcode and product_up.barcode != product.barcode:
        exists = session.exec(
            select(Product)
            .where(Product.barcode == product_up.barcode)
            .where(Product.id != product_id)
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="Barcode already in use")
    update_data = product_up.model_dump(exclude_unset=True)
    product.sqlmodel_update(update_data)

    session.add(product)
    session.commit()
    session.refresh(product)

    result = product.model_dump()
    result["images"] = [img.url for img in product.images]
    return result

@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir Produto",
    description="Exclui um produto e suas imagens associadas.",
    openapi_extra={
        "x-examples": {
            "Exemplo de Exclusão": {
                "summary": "Remover produto por ID",
                "value": {"product_id": "11111111-2222-3333-4444-555555555555"}
            }
        }
    }
)
def delete_product(
    session: SessionDep,
    product_id: UUID,
):
    """
    Regras de Negócio:
    - Todas as imagens associadas são removidas antes da exclusão do produto.
    - Retorna 404 se o produto não existir.

    Casos de Uso:
    - Remover produtos descontinuados ou incorretos do catálogo.
    """
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    session.exec(delete(ProductImage).where(ProductImage.product_id == product.id))
    session.delete(product)
    session.commit()
    return None
