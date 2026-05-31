from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.models import ApiResponse, ProxmoxNode, UserInfo
from src.proxmox import ProxmoxAdapterFactory, ProxmoxCredentials
from src.models import PlatformConfig
from src.crypto import decrypt_str
from src.utils import get_db_session, get_user_info
from src.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/nodes", tags=["Cluster Nodes"])


def _get_adapter(db_session: Session):
    config = db_session.exec(select(PlatformConfig)).first()
    if not config or not config.is_initialized:
        raise HTTPException(status_code=503, detail="Platform not initialized")
    token_secret = decrypt_str(config.encrypted_token_secret)
    credentials = ProxmoxCredentials(
        url=config.proxmox_url,
        token_id=config.token_id,
        token_secret=token_secret,
        verify_ssl=config.verify_ssl,
    )
    return ProxmoxAdapterFactory.create(config.proxmox_version, credentials)


@router.get("/list", response_model=ApiResponse)
def list_nodes(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    nodes = db_session.exec(select(ProxmoxNode)).all()
    return ApiResponse(
        message="Nodes retrieved",
        data={
            "nodes": [
                {
                    "id": n.id,
                    "name": n.node_name,
                    "hostname": n.node_name,
                    "cpu_count": n.cpu_count,
                    "cpu_usage": n.cpu_usage,
                    "memory_mb": round(n.memory_total / (1024 * 1024)) if n.memory_total else None,
                    "memory_used_mb": round(n.memory_used / (1024 * 1024)) if n.memory_used else None,
                    "status": n.status,
                    "uptime": n.uptime,
                    "last_seen_at": n.last_synced_at.isoformat() if n.last_synced_at else None,
                }
                for n in nodes
            ]
        },
    )


@router.get("/{node_name}/status", response_model=ApiResponse)
def get_node_status(
    node_name: str,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    node = db_session.exec(select(ProxmoxNode).where(ProxmoxNode.node_name == node_name)).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return ApiResponse(message="Node status", data=node.model_dump())


@router.post("/sync", response_model=ApiResponse)
def sync_nodes(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    from src.services.worker import sync_cluster_state
    sync_cluster_state.apply_async(ignore_result=True)
    return ApiResponse(message="Cluster sync queued")
