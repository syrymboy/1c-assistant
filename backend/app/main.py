import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import api, billing, chat, psp, sources

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # каталог источников подтягиваем из 1С при старте; если 1С недоступна, остаётся прежний каталог
    from app import catalog, onec
    from app.db import SessionLocal

    try:
        with SessionLocal() as db:
            log.info("Каталог 1С: %s", catalog.sync_catalog(db))
    except (onec.OneCError, Exception) as e:  # noqa: BLE001
        log.warning("Каталог 1С не обновлён: %s", e)
    yield


app = FastAPI(title="1C Assistant API", lifespan=lifespan)
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
