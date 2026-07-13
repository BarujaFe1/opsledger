import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import init_db

settings = get_settings()
logger = logging.getLogger("opsledger")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.demo_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("OpsLedger API ready · demo_dir=%s", settings.demo_dir)
    yield


app = FastAPI(title=settings.app_name, version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": {"message": "Payload inválido.", "code": "validation_error", "errors": exc.errors()}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": {"message": "Erro interno inesperado.", "code": "internal_error"}},
    )


# Prefixed for Vercel same-origin rewrites (/api/* → FastAPI service).
app.include_router(router, prefix="/api")
