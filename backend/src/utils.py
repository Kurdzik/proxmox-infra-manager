from fastapi import HTTPException, status
from sqlmodel import Session
from starlette.requests import Request

from src.models import UserInfo


def get_db_session(request: Request) -> Session:
    return request.state.db


def get_user_info(request: Request) -> UserInfo:
    return UserInfo(
        user_id=request.state.user_id,
        tenant_id=request.state.tenant_id,
        is_admin=getattr(request.state, "is_admin", False),
    )


def require_admin(user_info: UserInfo) -> None:
    if not user_info.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
