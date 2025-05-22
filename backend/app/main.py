from fastapi import FastAPI
from fastapi.routing import APIRoute
from app.api.main import api_router
from app.core.config import settings
from starlette.middleware.cors import CORSMiddleware

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"



app = FastAPI(
    root_path="/api",              # Requests are prefixed with /api
    title=settings.PROJECT_NAME,
    generate_unique_id_function=custom_generate_unique_id,
)
app.include_router(api_router)
app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
