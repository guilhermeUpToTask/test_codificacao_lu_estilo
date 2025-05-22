from fastapi import APIRouter
from app.api.routes import categories, tasks, users, login

api_router = APIRouter()
api_router.include_router(categories.router)
api_router.include_router(tasks.router)
api_router.include_router(login.router)
api_router.include_router(users.router)


