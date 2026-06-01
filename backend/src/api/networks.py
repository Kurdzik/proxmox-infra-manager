from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, and_, select

from src.logger import get_logger, tenant_context
from src.models import (
    ApiResponse,
    CreateVNetRequest,
    TenantVNet,
    UserInfo,
    VM,
    VNetResponse,
)
from src.services.tenant_network import (
    TenantNetworkError,
    create_named_vnet,
    get_platform_adapter,
)
from src.utils import get_db_session, get_user_info

logger = get_logger(__name__)
router = APIRouter(prefix="/networks", tags=["Networks"])


def _vnet_to_response(vnet: TenantVNet, vm_count: int) -> VNetResponse:
    return VNetResponse(
        id=vnet.id,
        vnet_id=vnet.vnet_id,
        name=vnet.name,
        is_default=vnet.is_default,
        subnet=vnet.subnet,
        gateway=vnet.gateway,
        dhcp_start=vnet.dhcp_start,
        dhcp_end=vnet.dhcp_end,
        vm_count=vm_count,
        created_at=vnet.created_at,
    )


@router.get("/list", response_model=ApiResponse)
def list_networks(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.networks"):
        vnets = db_session.exec(
            select(TenantVNet).where(TenantVNet.tenant_id == user_info.tenant_id)
        ).all()

        # Count VMs per network in one query
        counts_rows = db_session.exec(
            select(VM.network_id, func.count(VM.id))
            .where(VM.tenant_id == user_info.tenant_id, VM.network_id != None)  # noqa: E711
            .group_by(VM.network_id)
        ).all()
        counts = {row[0]: row[1] for row in counts_rows}

        return ApiResponse(
            message="ok",
            data={"networks": [_vnet_to_response(v, counts.get(v.id, 0)).model_dump() for v in vnets]},
        )


@router.post("/create", response_model=ApiResponse)
def create_network(
    request: CreateVNetRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.networks"):
        name = request.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name cannot be empty")

        try:
            adapter = get_platform_adapter(db_session)
            vnet = create_named_vnet(db_session, adapter, user_info.tenant_id, name)
        except TenantNetworkError as exc:
            db_session.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        logger.info("vnet_created", vnet_id=vnet.vnet_id, name=name, tenant=user_info.tenant_id)
        return ApiResponse(
            message="Network created",
            data={"network": _vnet_to_response(vnet, 0).model_dump()},
        )


@router.delete("/{network_id}", response_model=ApiResponse)
def delete_network(
    network_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.networks"):
        vnet = db_session.exec(
            select(TenantVNet).where(
                and_(TenantVNet.id == network_id, TenantVNet.tenant_id == user_info.tenant_id)
            )
        ).first()
        if not vnet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found")

        if vnet.is_default:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete the default network",
            )

        vm_count = db_session.exec(
            select(func.count(VM.id)).where(
                and_(VM.tenant_id == user_info.tenant_id, VM.network_id == network_id)
            )
        ).one()
        if vm_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete network with {vm_count} VM(s) attached. Remove or reassign VMs first.",
            )

        try:
            adapter = get_platform_adapter(db_session)
            adapter.delete_vnet(vnet.vnet_id)
        except Exception as exc:
            logger.warning("vnet_proxmox_delete_failed", vnet_id=vnet.vnet_id, error=str(exc))
            # Continue with DB removal even if Proxmox delete fails

        db_session.delete(vnet)
        db_session.commit()

        logger.info("vnet_deleted", vnet_id=vnet.vnet_id, name=vnet.name, tenant=user_info.tenant_id)
        return ApiResponse(message="Network deleted", data={})
