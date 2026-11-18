from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import api, billing, chat, psp, sources

app = FastAPI(title="1C Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api.router)
app.include_router(chat.router)
app.include_router(sources.router)
app.include_router(billing.router)
app.include_router(psp.router)
