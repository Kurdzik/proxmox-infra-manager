import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from src.crypto import hash_password, verify_password
from src.logger import get_logger
from src.models import (
    ApiResponse,
    ChangePasswordRequest,
    LoginRequest,
    PlatformConfig,
    RegisterRequest,
    TenantLogSettings,
    User,
    UserInfo,
)
from src.models import (
    Session as UserSession,
)
from src.services.tenant_network import ensure_tenant_vnet, get_platform_adapter
from src.utils import get_db_session, get_user_info

logger = get_logger(__name__)
router = APIRouter(prefix="/users", tags=["User Management"])

SESSION_EXPIRE_HOURS = 24 * 7  # 7 days


@router.post("/register", response_model=ApiResponse)
def register(request_body: RegisterRequest, request: Request, db_session: Session = Depends(get_db_session)):
    existing = db_session.exec(select(User).where(User.username == request_body.username)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    tenant_id = uuid.uuid4().hex
    is_first_user = db_session.exec(select(User)).first() is None

    hashed = hash_password(request_body.password)
    user = User(
        tenant_id=tenant_id,
        username=request_body.username,
        password=hashed,
        is_admin=is_first_user,  # First registered user becomes admin
    )
    db_session.add(user)

    # Provision tenant VNet synchronously
    config = db_session.exec(select(PlatformConfig)).first()
    if config and config.is_initialized:
        try:
            adapter = get_platform_adapter(db_session)
            ensure_tenant_vnet(db_session, adapter, tenant_id)
        except Exception as e:
            logger.warning("vnet_provisioning_failed", error=str(e))

    log_settings = TenantLogSettings(tenant_id=tenant_id)
    db_session.add(log_settings)

    db_session.commit()

    return ApiResponse(message="User registered successfully", data={"tenant_id": tenant_id})


@router.post("/login", response_model=ApiResponse)
def login(request_body: LoginRequest, request: Request, db_session: Session = Depends(get_db_session)):
    user = db_session.exec(select(User).where(User.username == request_body.username)).first()
    if not user or not verify_password(request_body.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    session = UserSession(
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=datetime.now() + timedelta(hours=SESSION_EXPIRE_HOURS),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    return ApiResponse(
        message="Login successful",
        data={"token": session.token, "is_admin": user.is_admin},
    )


@router.post("/logout", response_model=ApiResponse)
def logout(request: Request, db_session: Session = Depends(get_db_session)):
    token = request.headers.get("X-Session-Token")
    if token:
        session = db_session.exec(select(UserSession).where(UserSession.token == token)).first()
        if session:
            db_session.delete(session)
            db_session.commit()
    return ApiResponse(message="Logged out")


@router.post("/change-password", response_model=ApiResponse)
def change_password(
    request_body: ChangePasswordRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    user = db_session.exec(select(User).where(User.id == user_info.user_id)).first()
    if not user or not verify_password(request_body.old_password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")

    user.password = hash_password(request_body.new_password)
    db_session.add(user)
    db_session.commit()

    return ApiResponse(message="Password changed successfully")


@router.get("/me", response_model=ApiResponse)
def get_me(db_session: Session = Depends(get_db_session), user_info: UserInfo = Depends(get_user_info)):
    user = db_session.exec(select(User).where(User.id == user_info.user_id)).first()
    return ApiResponse(
        message="User info",
        data={"username": user.username, "tenant_id": user.tenant_id, "is_admin": user.is_admin},
    )
