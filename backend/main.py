import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import orders, payments, webhooks
from backend.core.config import settings
from backend.core.database import engine
from backend.domain import models
from backend.middleware.error_handler import ErrorHandlerMiddleware
from backend.middleware.logging import LoggingMiddleware
from backend.tasks.polling_task import polling_worker

models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(polling_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorHandlerMiddleware)

app.include_router(payments.router, prefix=settings.API_V1_PREFIX)
app.include_router(orders.router, prefix=settings.API_V1_PREFIX)
app.include_router(webhooks.router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root() -> dict:
    return {
        "message": "Payment Service API",
        "version": settings.VERSION,
        "docs": "/docs",
        "webhook_url": f"{settings.API_V1_PREFIX}/webhooks/bank"
    }


@app.get("/health")
async def health_check() -> dict:
    return {"status": "healthy"}
