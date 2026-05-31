from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, and_

from src.models import ApiResponse, DockerService, DNSEntry, NginxConfig, VM, Container, UserInfo
from src.utils import get_db_session, get_user_info
from src.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/services", tags=["Service Registry"])


@router.get("/list", response_model=ApiResponse)
def list_services(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    services = db_session.exec(
        select(DockerService).where(DockerService.tenant_id == user_info.tenant_id)
    ).all()

    enriched = []
    for svc in services:
        dns = None
        nginx = None
        if svc.dns_entry_id:
            dns = db_session.exec(select(DNSEntry).where(DNSEntry.id == svc.dns_entry_id)).first()
        if svc.nginx_config_id:
            nginx = db_session.exec(select(NginxConfig).where(NginxConfig.id == svc.nginx_config_id)).first()

        enriched.append({
            **svc.model_dump(),
            "dns": dns.model_dump() if dns else None,
            "nginx": {"server_name": nginx.server_name, "proxy_type": nginx.proxy_type} if nginx else None,
        })

    return ApiResponse(message="Services retrieved", data={"services": enriched})


@router.get("/{service_id}", response_model=ApiResponse)
def get_service(
    service_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    svc = db_session.exec(
        select(DockerService).where(
            and_(DockerService.tenant_id == user_info.tenant_id, DockerService.id == service_id)
        )
    ).first()
    if not svc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    dns = db_session.exec(select(DNSEntry).where(DNSEntry.id == svc.dns_entry_id)).first() if svc.dns_entry_id else None
    nginx = db_session.exec(select(NginxConfig).where(NginxConfig.id == svc.nginx_config_id)).first() if svc.nginx_config_id else None

    return ApiResponse(
        message="Service retrieved",
        data={
            **svc.model_dump(),
            "dns": dns.model_dump() if dns else None,
            "nginx": nginx.model_dump() if nginx else None,
        },
    )
