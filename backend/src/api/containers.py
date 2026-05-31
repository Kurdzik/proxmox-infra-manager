from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, and_

from src.models import (
    ApiResponse, Container, CTTemplate, UserInfo,
    CreateCTTemplateRequest, ProvisionCTRequest,
)
from src.utils import get_db_session, get_user_info
from src.logger import get_logger, tenant_context

logger = get_logger(__name__)
router = APIRouter(prefix="/containers", tags=["Container Provisioning"])


@router.get("/list", response_model=ApiResponse)
def list_containers(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.containers"):
        cts = db_session.exec(
            select(Container).where(Container.tenant_id == user_info.tenant_id)
        ).all()
        return ApiResponse(message="Containers retrieved", data={"containers": [c.model_dump() for c in cts]})


@router.get("/{ct_id}", response_model=ApiResponse)
def get_container(
    ct_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.containers"):
        ct = db_session.exec(
            select(Container).where(and_(Container.tenant_id == user_info.tenant_id, Container.id == ct_id))
        ).first()
        if not ct:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
        return ApiResponse(message="Container retrieved", data=ct.model_dump())


@router.post("/provision", response_model=ApiResponse)
def provision_ct(
    request: ProvisionCTRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.containers"):
        template = db_session.exec(
            select(CTTemplate).where(
                and_(CTTemplate.tenant_id == user_info.tenant_id, CTTemplate.id == request.template_id)
            )
        ).first()
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

        from src.services.worker import provision_ct as provision_ct_task
        task = provision_ct_task.apply_async(
            kwargs={
                "template_id": request.template_id,
                "node_name": request.node_name,
                "ct_name": request.ct_name,
                "tenant_id": user_info.tenant_id,
            },
            ignore_result=True,
        )
        return ApiResponse(message="Container provisioning queued", data={"task_id": task.id})


@router.delete("/{ct_id}", response_model=ApiResponse)
def destroy_container(
    ct_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.containers"):
        ct = db_session.exec(
            select(Container).where(and_(Container.tenant_id == user_info.tenant_id, Container.id == ct_id))
        ).first()
        if not ct:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")

        from src.services.worker import destroy_ct
        destroy_ct.apply_async(
            kwargs={"ct_id": ct_id, "tenant_id": user_info.tenant_id},
            ignore_result=True,
        )
        return ApiResponse(message="Container destruction queued")


@router.get("/templates/list", response_model=ApiResponse)
def list_ct_templates(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    templates = db_session.exec(
        select(CTTemplate).where(CTTemplate.tenant_id == user_info.tenant_id)
    ).all()
    return ApiResponse(message="Templates retrieved", data={"templates": [t.model_dump() for t in templates]})


@router.post("/templates", response_model=ApiResponse)
def create_ct_template(
    request: CreateCTTemplateRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    template = CTTemplate(tenant_id=user_info.tenant_id, **request.model_dump())
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return ApiResponse(message="Template created", data={"id": template.id})


@router.delete("/templates/{template_id}", response_model=ApiResponse)
def delete_ct_template(
    template_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    template = db_session.exec(
        select(CTTemplate).where(
            and_(CTTemplate.tenant_id == user_info.tenant_id, CTTemplate.id == template_id)
        )
    ).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    db_session.delete(template)
    db_session.commit()
    return ApiResponse(message="Template deleted")
