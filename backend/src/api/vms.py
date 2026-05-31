from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, and_

from src.images import COMMON_IMAGES, parse_storage_path
from src.models import (
    ApiResponse, VM, VMTemplate, UserInfo, PlatformConfig,
    CreateVMTemplateRequest, ProvisionVMRequest,
)
from src.utils import get_db_session, get_user_info
from src.logger import get_logger, tenant_context

logger = get_logger(__name__)
router = APIRouter(prefix="/vms", tags=["VM Provisioning"])


@router.get("/list", response_model=ApiResponse)
def list_vms(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.vms"):
        vms = db_session.exec(select(VM).where(VM.tenant_id == user_info.tenant_id)).all()
        return ApiResponse(message="VMs retrieved", data={"vms": [v.model_dump() for v in vms]})


@router.get("/images", response_model=ApiResponse)
def list_images(
    node: str | None = None,
    storage: str = "local",
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    """Return the curated image list annotated with availability on the given node/storage."""
    existing_filenames: set[str] = set()

    if node:
        try:
            config = db_session.exec(select(PlatformConfig)).first()
            if config and config.is_initialized:
                from src.crypto import decrypt_str
                from src.proxmox import ProxmoxAdapterFactory, ProxmoxCredentials
                creds = ProxmoxCredentials(
                    url=config.proxmox_url,
                    token_id=config.token_id,
                    token_secret=decrypt_str(config.encrypted_token_secret),
                    verify_ssl=config.verify_ssl,
                )
                adapter = ProxmoxAdapterFactory.create(config.proxmox_version, creds)
                content = adapter.list_storage_content(node, storage, "iso")
                for item in content:
                    volid = item.get("volid", "")
                    fname = volid.split("/")[-1] if "/" in volid else volid
                    existing_filenames.add(fname)
        except Exception:
            pass  # Storage check is best-effort; still return the list

    images = []
    for img in COMMON_IMAGES:
        images.append({
            **img,
            "available": img["filename"] in existing_filenames,
        })

    return ApiResponse(message="Images retrieved", data={"images": images, "storage": storage})


@router.get("/{vm_id}", response_model=ApiResponse)
def get_vm(
    vm_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.vms"):
        vm = db_session.exec(
            select(VM).where(and_(VM.tenant_id == user_info.tenant_id, VM.id == vm_id))
        ).first()
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
        return ApiResponse(message="VM retrieved", data=vm.model_dump())


@router.post("/provision", response_model=ApiResponse)
def provision_vm(
    request: ProvisionVMRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.vms"):
        # Resolve template: use existing template_id, or auto-create one from image_id
        if request.template_id:
            template = db_session.exec(
                select(VMTemplate).where(
                    and_(VMTemplate.tenant_id == user_info.tenant_id, VMTemplate.id == request.template_id)
                )
            ).first()
            if not template:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
            template_id = request.template_id
        elif request.image_id and request.os_image:
            from src.images import IMAGE_BY_ID
            img = IMAGE_BY_ID.get(request.image_id)
            if not img:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown image: {request.image_id}")
            template = VMTemplate(
                tenant_id=user_info.tenant_id,
                name=img["name"],
                cores=2,
                memory_mb=2048,
                disk_gb=20,
                os_image=request.os_image,
                network_model="virtio",
            )
            db_session.add(template)
            db_session.commit()
            db_session.refresh(template)
            template_id = template.id
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide template_id or image_id+os_image")

        from src.services.worker import provision_vm as provision_vm_task
        task = provision_vm_task.apply_async(
            kwargs={
                "template_id": template_id,
                "node_name": request.node_name,
                "vm_name": request.vm_name,
                "tenant_id": user_info.tenant_id,
            },
            ignore_result=True,
        )

        return ApiResponse(message="VM provisioning queued", data={"task_id": task.id})


@router.delete("/{vm_id}", response_model=ApiResponse)
def destroy_vm(
    vm_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.vms"):
        vm = db_session.exec(
            select(VM).where(and_(VM.tenant_id == user_info.tenant_id, VM.id == vm_id))
        ).first()
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")

        from src.services.worker import destroy_vm as destroy_vm_task
        destroy_vm_task.apply_async(
            kwargs={"vm_id": vm_id, "tenant_id": user_info.tenant_id},
            ignore_result=True,
        )

        return ApiResponse(message="VM destruction queued")


# VM Templates
DEFAULT_TEMPLATES = [
    {
        "name": "Ubuntu 24.04 LTS",
        "cores": 2,
        "memory_mb": 2048,
        "disk_gb": 20,
        "os_image": "local:iso/ubuntu-24.04-live-server-amd64.iso",
        "network_model": "virtio",
    },
    {
        "name": "Ubuntu 22.04 LTS",
        "cores": 2,
        "memory_mb": 2048,
        "disk_gb": 20,
        "os_image": "local:iso/ubuntu-22.04.4-live-server-amd64.iso",
        "network_model": "virtio",
    },
]


@router.get("/templates/list", response_model=ApiResponse)
def list_templates(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    templates = db_session.exec(
        select(VMTemplate).where(VMTemplate.tenant_id == user_info.tenant_id)
    ).all()

    # Auto-seed defaults on first use
    if not templates:
        for t in DEFAULT_TEMPLATES:
            tpl = VMTemplate(tenant_id=user_info.tenant_id, **t)
            db_session.add(tpl)
        db_session.commit()
        templates = db_session.exec(
            select(VMTemplate).where(VMTemplate.tenant_id == user_info.tenant_id)
        ).all()

    return ApiResponse(message="Templates retrieved", data={"templates": [t.model_dump() for t in templates]})


@router.post("/templates", response_model=ApiResponse)
def create_template(
    request: CreateVMTemplateRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    template = VMTemplate(tenant_id=user_info.tenant_id, **request.model_dump())
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return ApiResponse(message="Template created", data={"id": template.id})


@router.delete("/templates/{template_id}", response_model=ApiResponse)
def delete_template(
    template_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    template = db_session.exec(
        select(VMTemplate).where(
            and_(VMTemplate.tenant_id == user_info.tenant_id, VMTemplate.id == template_id)
        )
    ).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    db_session.delete(template)
    db_session.commit()
    return ApiResponse(message="Template deleted")
