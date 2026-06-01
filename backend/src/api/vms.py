from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, and_, select

from src.images import COMMON_IMAGES, IMAGE_BY_ID
from src.logger import get_logger, tenant_context
from src.models import (
    VM,
    ApiResponse,
    CreateVMTemplateRequest,
    PlatformConfig,
    ProvisionVMRequest,
    TenantVNet,
    UserInfo,
    VMSSHKey,
    VMTemplate,
)
from src.services.tenant_network import TenantNetworkError
from src.utils import get_db_session, get_user_info

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
    """Return the curated cloud-image list annotated with availability on the given node/storage."""
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
            pass  # Storage check is best-effort

    # Only expose cloud-image type images — provisioning now requires cloud-init
    images = []
    for img in COMMON_IMAGES:
        if img.get("image_type") == "cloud-image":
            images.append({
                **img,
                "available": img["filename"] in existing_filenames,
            })

    return ApiResponse(message="Images retrieved", data={"images": images, "storage": storage})


@router.get("/{vm_id}/console-credentials", response_model=ApiResponse)
def get_vm_console_credentials(
    vm_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    """Return the console username and password for serial console (termproxy) access."""
    from src.crypto import decrypt_str
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.vms"):
        vm = db_session.exec(
            select(VM).where(and_(VM.tenant_id == user_info.tenant_id, VM.id == vm_id))
        ).first()
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
        if not vm.console_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No console credentials — VM was provisioned before this feature was added",
            )
        return ApiResponse(
            message="Console credentials retrieved",
            data={
                "username": vm.cloud_init_user or "ubuntu",
                "password": decrypt_str(vm.console_password_encrypted),
            },
        )


@router.get("/{vm_id}/ssh-key", response_model=ApiResponse)
def get_vm_ssh_key(
    vm_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.vms"):
        ssh_key = db_session.exec(
            select(VMSSHKey).where(
                and_(VMSSHKey.tenant_id == user_info.tenant_id, VMSSHKey.vm_id == vm_id)
            )
        ).first()
        if not ssh_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSH key not found for this VM")
        return ApiResponse(
            message="SSH key retrieved",
            data={"vm_id": vm_id, "public_key": ssh_key.public_key, "key_type": ssh_key.key_type},
        )


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
        # Validate image exists and is a cloud-image
        img = IMAGE_BY_ID.get(request.image_id)
        if not img:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown image: {request.image_id}",
            )
        if img.get("image_type") != "cloud-image":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only cloud-image type images are supported for provisioning",
            )

        # Resolve bridge: explicit override → specific VNet by ID → None (worker auto-creates per-VM VNet).
        bridge = request.bridge
        resolved_network_id: int | None = None
        if not bridge and request.network_id is not None:
            vnet = db_session.exec(
                select(TenantVNet).where(
                    and_(
                        TenantVNet.id == request.network_id,
                        TenantVNet.tenant_id == user_info.tenant_id,
                    )
                )
            ).first()
            if not vnet:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Network {request.network_id} not found",
                )
            bridge = vnet.vnet_id
            resolved_network_id = vnet.id
        # When bridge and resolved_network_id are both None the Celery worker
        # will auto-create an isolated per-VM VNet during provisioning.

        vm = VM(
            tenant_id=user_info.tenant_id,
            vmid=0,  # placeholder; worker assigns the real Proxmox VMID
            node_name=request.node_name,
            name=request.vm_name,
            status="provisioning",
            cpu_cores=request.cpu_cores,
            memory_mb=request.memory_mb,
            disk_gb=request.disk_gb,
            cloud_init_user=request.cloud_init_user,
            network_id=resolved_network_id,
            auth_type=request.auth_type,
        )
        db_session.add(vm)
        db_session.commit()
        db_session.refresh(vm)

        from src.services.worker import provision_vm as provision_vm_task
        task = provision_vm_task.apply_async(
            kwargs={
                "vm_id": vm.id,
                "node_name": request.node_name,
                "vm_name": request.vm_name,
                "tenant_id": user_info.tenant_id,
                "image_id": request.image_id,
                "cpu_cores": request.cpu_cores,
                "memory_mb": request.memory_mb,
                "disk_gb": request.disk_gb,
                "cloud_init_user": request.cloud_init_user,
                "bridge": bridge,
                "network_id": resolved_network_id,
                "user_ssh_key_ids": request.user_ssh_key_ids,
                "auth_type": request.auth_type,
                "user_password": request.user_password,
            },
            ignore_result=True,
        )

        vm.task_id = task.id
        db_session.add(vm)
        db_session.commit()

        return ApiResponse(message="VM provisioning queued", data={"task_id": task.id, "vm_id": vm.id})



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


# VM Templates (retained for user-defined configurations)
DEFAULT_TEMPLATES = [
    {
        "name": "Ubuntu 24.04 LTS Cloud",
        "cores": 2,
        "memory_mb": 2048,
        "disk_gb": 20,
        "os_image": "local:iso/ubuntu-24.04-server-cloudimg-amd64.img",
        "image_type": "cloud-image",
        "network_model": "virtio",
    },
    {
        "name": "Ubuntu 22.04 LTS Cloud",
        "cores": 2,
        "memory_mb": 2048,
        "disk_gb": 20,
        "os_image": "local:iso/ubuntu-22.04-server-cloudimg-amd64.img",
        "image_type": "cloud-image",
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
