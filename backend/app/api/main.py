from fastapi import APIRouter
from app.api.routes import clients, orders, products, users
from app.api.routes import auth

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(clients.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)


