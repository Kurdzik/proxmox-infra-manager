import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, and_, select

from src.crypto import decrypt_str
from src.logger import get_logger, tenant_context
from src.models import (
    VM,
    ApiResponse,
    AppCatalogEntry,
    AppInstance,
    AppPlaybook,
    AppVersion,
    ProvisionAppRequest,
    UserInfo,
)
from src.utils import get_db_session, get_user_info

logger = get_logger(__name__)
router = APIRouter(prefix="/apps", tags=["Apps"])


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@router.get("/catalog", response_model=ApiResponse)
def get_catalog(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    entries = db_session.exec(select(AppCatalogEntry)).all()
    result = []
    for entry in entries:
        versions = db_session.exec(
            select(AppVersion)
            .where(AppVersion.catalog_entry_id == entry.id)
            .order_by(AppVersion.version.desc())
        ).all()
        result.append({
            **entry.model_dump(),
            "versions": [v.model_dump() for v in versions],
        })
    return ApiResponse(message="App catalog retrieved", data={"catalog": result})


# ---------------------------------------------------------------------------
# App instances
# ---------------------------------------------------------------------------

@router.get("/list", response_model=ApiResponse)
def list_apps(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.apps"):
        instances = db_session.exec(
            select(AppInstance).where(AppInstance.tenant_id == user_info.tenant_id)
        ).all()

        result = []
        for inst in instances:
            catalog = db_session.exec(
                select(AppCatalogEntry).where(AppCatalogEntry.id == inst.catalog_entry_id)
            ).first()
            result.append({
                **inst.model_dump(),
                "catalog_name": catalog.name if catalog else None,
                "catalog_slug": catalog.slug if catalog else None,
            })

        return ApiResponse(message="Apps retrieved", data={"apps": result})


@router.get("/{app_id}", response_model=ApiResponse)
def get_app(
    app_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.apps"):
        inst = db_session.exec(
            select(AppInstance).where(
                and_(AppInstance.tenant_id == user_info.tenant_id, AppInstance.id == app_id)
            )
        ).first()
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

        catalog = db_session.exec(
            select(AppCatalogEntry).where(AppCatalogEntry.id == inst.catalog_entry_id)
        ).first()

        # Decrypt and expose connection credentials
        connection_user = None
        connection_password = None
        if inst.connection_credentials:
            try:
                creds = json.loads(decrypt_str(inst.connection_credentials))
                connection_user = creds.get("db_user")
                connection_password = creds.get("db_password")
            except Exception:
                pass

        # Resolve the VM IP for connection host
        connection_host = None
        if inst.vm_id:
            vm = db_session.exec(select(VM).where(VM.id == inst.vm_id)).first()
            if vm:
                connection_host = vm.ip_address

        # Use the nginx external port as the connection port shown to users
        connection_port = inst.external_port or inst.internal_port

        data = {
            **inst.model_dump(),
            "catalog_name": catalog.name if catalog else None,
            "catalog_slug": catalog.slug if catalog else None,
            "connection_host": connection_host,
            "connection_port": connection_port,
            "connection_user": connection_user,
            "connection_password": connection_password,
        }
        return ApiResponse(message="App retrieved", data={"app": data})


# ---------------------------------------------------------------------------
# Provision
# ---------------------------------------------------------------------------

@router.post("/provision", response_model=ApiResponse)
def provision_app(
    req: ProvisionAppRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.apps"):
        catalog = db_session.exec(
            select(AppCatalogEntry).where(AppCatalogEntry.id == req.catalog_entry_id)
        ).first()
        if not catalog:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App type not found")

        version = db_session.exec(
            select(AppVersion).where(
                and_(
                    AppVersion.id == req.version_id,
                    AppVersion.catalog_entry_id == req.catalog_entry_id,
                )
            )
        ).first()
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="App version not found"
            )

        # Check a playbook exists for this catalog entry
        playbook = db_session.exec(
            select(AppPlaybook).where(
                and_(
                    AppPlaybook.catalog_entry_id == req.catalog_entry_id,
                    AppPlaybook.version_id == req.version_id,
                )
            )
        ).first()
        if not playbook:
            # Fall back to version-agnostic playbook
            playbook = db_session.exec(
                select(AppPlaybook).where(
                    and_(
                        AppPlaybook.catalog_entry_id == req.catalog_entry_id,
                        AppPlaybook.version_id == None,  # noqa: E711
                    )
                )
            ).first()
        if not playbook:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No playbook found for {catalog.name} {version.version}",
            )

        app_instance = AppInstance(
            tenant_id=user_info.tenant_id,
            name=req.app_name,
            catalog_entry_id=req.catalog_entry_id,
            version=version.version,
            node_name=req.node_name,
            status="provisioning",
            internal_port=catalog.default_port,
        )
        db_session.add(app_instance)
        db_session.commit()
        db_session.refresh(app_instance)

        from src.services.worker import provision_app_task
        task = provision_app_task.delay(
            app_instance_id=app_instance.id,
            tenant_id=user_info.tenant_id,
            catalog_entry_id=req.catalog_entry_id,
            version_id=req.version_id,
            app_name=req.app_name,
            node_name=req.node_name,
            image_id=req.image_id,
            cpu_cores=req.cpu_cores,
            memory_mb=req.memory_mb,
            disk_gb=req.disk_gb,
            network_id=req.network_id,
        )
        app_instance.task_id = task.id
        db_session.add(app_instance)
        db_session.commit()

        logger.info(
            "app_provision_enqueued",
            app_id=app_instance.id,
            app_name=req.app_name,
            catalog=catalog.slug,
            version=version.version,
            persist_db=True,
        )
        return ApiResponse(
            message="App provisioning started",
            data={"app_id": app_instance.id, "task_id": task.id},
        )


# ---------------------------------------------------------------------------
# Start / Stop
# ---------------------------------------------------------------------------

@router.post("/{app_id}/start", response_model=ApiResponse)
def start_app(
    app_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.apps"):
        inst = db_session.exec(
            select(AppInstance).where(
                and_(AppInstance.tenant_id == user_info.tenant_id, AppInstance.id == app_id)
            )
        ).first()
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

        from src.services.worker import control_app_service_task
        task = control_app_service_task.delay(
            app_instance_id=app_id,
            tenant_id=user_info.tenant_id,
            action="start",
        )
        return ApiResponse(
            message="Start command sent",
            data={"task_id": task.id},
        )


@router.post("/{app_id}/stop", response_model=ApiResponse)
def stop_app(
    app_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.apps"):
        inst = db_session.exec(
            select(AppInstance).where(
                and_(AppInstance.tenant_id == user_info.tenant_id, AppInstance.id == app_id)
            )
        ).first()
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

        from src.services.worker import control_app_service_task
        task = control_app_service_task.delay(
            app_instance_id=app_id,
            tenant_id=user_info.tenant_id,
            action="stop",
        )
        return ApiResponse(
            message="Stop command sent",
            data={"task_id": task.id},
        )


# ---------------------------------------------------------------------------
# Destroy
# ---------------------------------------------------------------------------

@router.delete("/{app_id}", response_model=ApiResponse)
def destroy_app(
    app_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.apps"):
        inst = db_session.exec(
            select(AppInstance).where(
                and_(AppInstance.tenant_id == user_info.tenant_id, AppInstance.id == app_id)
            )
        ).first()
        if not inst:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App not found")

        if inst.status in ("provisioning", "configuring"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot destroy an app that is still being provisioned",
            )

        from src.services.worker import destroy_app_task
        task = destroy_app_task.delay(
            app_instance_id=app_id,
            tenant_id=user_info.tenant_id,
        )
        return ApiResponse(
            message="App destruction started",
            data={"task_id": task.id},
        )
