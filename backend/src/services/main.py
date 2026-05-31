import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy import create_engine
from starlette.exceptions import HTTPException as StarletteHTTPException

from src import configure_logger, get_logger, log_context
from src.middleware import (
    InitGateMiddleware,
    RequestContextMiddleware,
    SQLAlchemySessionMiddleware,
    session,
)
from src.models import *
from src.api import api_router, public_router

load_dotenv()

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api.system")
logger = get_logger("api.system")

app = FastAPI(
    title="Infra Manager",
    redoc_url="/docs",
    docs_url=None,
    default_response_class=ORJSONResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
        503: {"model": ErrorResponse, "description": "Platform not initialized"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(InitGateMiddleware)
app.add_middleware(SQLAlchemySessionMiddleware, db_session_factory=session)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(status_code: int, detail: str, request: Request) -> ORJSONResponse:
    request_id = getattr(request.state, "request_id", None)
    payload = {"detail": detail}
    if request_id:
        payload["request_id"] = request_id
    return ORJSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"

    level = "error" if status_code >= 500 else "warning"
    with log_context(request_id=request_id, service_name="api.error"):
        getattr(logger, level)(
            "http_exception",
            status_code=status_code,
            detail=detail,
            method=request.method,
            path=request.url.path,
        )

    return _error_response(status_code, detail, request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    with log_context(request_id=request_id, service_name="api.error"):
        logger.warning(
            "request_validation_failed",
            method=request.method,
            path=request.url.path,
            errors=exc.errors(),
        )
    return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid request payload", request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    with log_context(
        request_id=request_id,
        tenant_id=getattr(request.state, "tenant_id", None),
        service_name="api.error",
    ):
        logger.error(
            "unhandled_exception",
            method=request.method,
            path=request.url.path,
            error=str(exc),
            exc_info=True,
        )
    detail = "Internal server error"
    if request_id:
        detail = f"{detail}. Reference: {request_id}"
    return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, detail, request)


app.include_router(public_router)
app.include_router(api_router)
