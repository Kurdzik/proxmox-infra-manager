import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status, Security
from fastapi.responses import ORJSONResponse
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.security.api_key import APIKeyHeader
from src.models import Session as UserSession, User, PlatformConfig
from src.logger import get_logger, log_context

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
logger = get_logger(__name__)
session_token_header = APIKeyHeader(name="X-Session-Token", auto_error=False)


def session() -> Session:
    return Session(engine)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        with log_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            service_name="api.request",
        ):
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response


class SQLAlchemySessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, db_session_factory):
        super().__init__(app)
        self.db_session_factory = db_session_factory

    async def dispatch(self, request: Request, call_next):
        request.state.db = self.db_session_factory()
        try:
            response = await call_next(request)
            request.state.db.commit()
        except SQLAlchemyError:
            request.state.db.rollback()
            raise
        finally:
            request.state.db.close()
        return response


class InitGateMiddleware(BaseHTTPMiddleware):
    """Blocks all requests until the platform is initialized via POST /api/v1/init/configure."""

    EXCLUDED_PATHS = {
        "/api/v1/init/configure",
        "/api/v1/init/status",
        "/api/v1/init/test-connection",
        "/api/v1/users/register",
        "/api/v1/users/login",
        "/api/v1/users/change-password",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXCLUDED_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        config = request.state.db.exec(select(PlatformConfig)).first()
        if not config or not config.is_initialized:
            return ORJSONResponse(
                status_code=503,
                content={"detail": "Platform not initialized. Complete setup at /init."},
            )

        return await call_next(request)


def check_token(request: Request, token: str = Security(session_token_header)):
    request.state.user_id = None
    request.state.tenant_id = None
    request.state.is_admin = False

    excluded_paths = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/users/register",
        "/api/v1/users/login",
        "/api/v1/init/configure",
        "/api/v1/init/status",
        "/api/v1/init/test-connection",
    ]

    if request.url.path in excluded_paths or request.method == "OPTIONS":
        return

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token required",
        )

    try:
        user_session = request.state.db.exec(
            select(UserSession).where(UserSession.token == token)
        ).one()

        user = request.state.db.exec(
            select(User).where(User.id == user_session.user_id)
        ).one()

        request.state.user_id = user_session.user_id
        request.state.tenant_id = user.tenant_id
        request.state.is_admin = user.is_admin

    except Exception as e:
        logger.warning("auth_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )
