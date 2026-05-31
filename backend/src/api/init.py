from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.models import ApiResponse, InitConfigureRequest, PlatformConfig
from src.proxmox import ProxmoxAdapterFactory, ProxmoxCredentials
from src.crypto import encrypt_str
from src.utils import get_db_session, get_user_info, require_admin
from src.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/init", tags=["Platform Initialization"])


@router.get("/status", response_model=ApiResponse)
def get_init_status(db_session: Session = Depends(get_db_session)):
    config = db_session.exec(select(PlatformConfig)).first()
    return ApiResponse(
        message="Platform status",
        data={
            "is_initialized": bool(config and config.is_initialized),
            "proxmox_version": config.proxmox_version if config else None,
        },
    )


@router.post("/test-connection", response_model=ApiResponse)
def test_connection(request: InitConfigureRequest):
    credentials = ProxmoxCredentials(
        url=request.proxmox_url,
        token_id=request.token_id,
        token_secret=request.token_secret,
        verify_ssl=request.verify_ssl,
    )
    try:
        adapter = ProxmoxAdapterFactory.create(request.proxmox_version, credentials)
        nodes = adapter.list_nodes()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reach Proxmox API: {str(e)}",
        )
    node_names = [n.get("node") for n in nodes] if isinstance(nodes, list) else []
    return ApiResponse(
        message="Connection successful",
        data={"nodes": node_names},
    )


@router.post("/configure", response_model=ApiResponse)
def configure_platform(
    request: InitConfigureRequest,
    db_session: Session = Depends(get_db_session),
):
    credentials = ProxmoxCredentials(
        url=request.proxmox_url,
        token_id=request.token_id,
        token_secret=request.token_secret,
        verify_ssl=request.verify_ssl,
    )

    try:
        adapter = ProxmoxAdapterFactory.create(request.proxmox_version, credentials)
        nodes = adapter.list_nodes()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reach Proxmox API: {str(e)}",
        )

    encrypted_secret = encrypt_str(request.token_secret)

    config = db_session.exec(select(PlatformConfig)).first()
    if config:
        config.proxmox_url = request.proxmox_url
        config.proxmox_version = request.proxmox_version
        config.token_id = request.token_id
        config.encrypted_token_secret = encrypted_secret
        config.verify_ssl = request.verify_ssl
        config.is_initialized = True
    else:
        config = PlatformConfig(
            proxmox_url=request.proxmox_url,
            proxmox_version=request.proxmox_version,
            token_id=request.token_id,
            encrypted_token_secret=encrypted_secret,
            verify_ssl=request.verify_ssl,
            is_initialized=True,
        )
        db_session.add(config)

    db_session.commit()

    return ApiResponse(
        message="Platform initialized successfully",
        data={"node_count": len(nodes) if isinstance(nodes, list) else 0},
    )


@router.get("/config", response_model=ApiResponse)
def get_config(
    db_session: Session = Depends(get_db_session),
    user_info=Depends(get_user_info),
):
    require_admin(user_info)
    config = db_session.exec(select(PlatformConfig)).first()
    if not config or not config.is_initialized:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not configured")
    return ApiResponse(
        message="Platform config",
        data={
            "proxmox_url": config.proxmox_url,
            "proxmox_version": config.proxmox_version,
            "token_id": config.token_id,
            "verify_ssl": config.verify_ssl,
        },
    )


@router.post("/reset", response_model=ApiResponse)
def reset_platform(
    db_session: Session = Depends(get_db_session),
    user_info=Depends(get_user_info),
):
    require_admin(user_info)

    config = db_session.exec(select(PlatformConfig)).first()
    if config:
        config.is_initialized = False
        config.encrypted_token_secret = None
        db_session.add(config)
        db_session.commit()

    return ApiResponse(message="Platform reset. Re-run the setup wizard.")
