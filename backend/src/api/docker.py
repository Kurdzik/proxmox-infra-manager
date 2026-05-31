from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, and_

from src.models import ApiResponse, DockerService, UserInfo, DeployDockerServiceRequest
from src.utils import get_db_session, get_user_info
from src.logger import get_logger, tenant_context

logger = get_logger(__name__)
router = APIRouter(prefix="/docker", tags=["Docker Services"])


@router.get("/list", response_model=ApiResponse)
def list_services(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.docker"):
        services = db_session.exec(
            select(DockerService).where(DockerService.tenant_id == user_info.tenant_id)
        ).all()
        return ApiResponse(
            message="Services retrieved",
            data={"services": [s.model_dump() for s in services]},
        )


@router.get("/{service_id}", response_model=ApiResponse)
def get_service(
    service_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.docker"):
        svc = db_session.exec(
            select(DockerService).where(
                and_(DockerService.tenant_id == user_info.tenant_id, DockerService.id == service_id)
            )
        ).first()
        if not svc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
        return ApiResponse(message="Service retrieved", data=svc.model_dump())


@router.post("/deploy", response_model=ApiResponse)
def deploy_service(
    request: DeployDockerServiceRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.docker"):
        from src.services.worker import deploy_docker_service
        task = deploy_docker_service.apply_async(
            kwargs={
                "target_vmid": request.target_vmid,
                "target_type": request.target_type,
                "node_name": request.node_name,
                "service_name": request.service_name,
                "image_name": request.image_name,
                "image_tag": request.image_tag,
                "internal_port": request.internal_port,
                "external_port": request.external_port,
                "proxy_type": request.proxy_type,
                "dns_hostname": request.dns_hostname,
                "tenant_id": user_info.tenant_id,
            },
            ignore_result=True,
        )
        return ApiResponse(message="Docker deployment queued", data={"task_id": task.id})


@router.delete("/{service_id}", response_model=ApiResponse)
def remove_service(
    service_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.docker"):
        svc = db_session.exec(
            select(DockerService).where(
                and_(DockerService.tenant_id == user_info.tenant_id, DockerService.id == service_id)
            )
        ).first()
        if not svc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

        from src.services.worker import remove_docker_service
        remove_docker_service.apply_async(
            kwargs={"service_id": service_id, "tenant_id": user_info.tenant_id},
            ignore_result=True,
        )
        return ApiResponse(message="Service removal queued")
