from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.models import ApiResponse, Plugin, PluginCapabilityCache, UserInfo, InstallPluginRequest
from src.utils import get_db_session, get_user_info, require_admin
from src.plugin_manager import IntegrationClient
from src.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/plugins", tags=["Plugin Management"])


@router.get("/list", response_model=ApiResponse)
def list_plugins(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    plugins = db_session.exec(select(Plugin)).all()
    return ApiResponse(message="Plugins retrieved", data={"plugins": [p.model_dump() for p in plugins]})


@router.post("/install", response_model=ApiResponse)
def install_plugin(
    request: InstallPluginRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    require_admin(user_info)

    from src.services.worker import install_plugin as install_plugin_task
    task = install_plugin_task.apply_async(
        kwargs={
            "repo_url": request.repo_url,
            "auth_token": request.auth_token,
            "env_overrides": request.env_overrides,
        },
        ignore_result=True,
    )
    return ApiResponse(message="Plugin installation queued", data={"task_id": task.id})


@router.delete("/{plugin_id}", response_model=ApiResponse)
def uninstall_plugin(
    plugin_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    require_admin(user_info)

    plugin = db_session.exec(select(Plugin).where(Plugin.id == plugin_id)).first()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")

    from src.services.worker import uninstall_plugin as uninstall_plugin_task
    uninstall_plugin_task.apply_async(kwargs={"plugin_id": plugin_id}, ignore_result=True)
    return ApiResponse(message="Plugin uninstall queued")


@router.post("/{plugin_id}/update", response_model=ApiResponse)
def update_plugin(
    plugin_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    require_admin(user_info)

    plugin = db_session.exec(select(Plugin).where(Plugin.id == plugin_id)).first()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")

    from src.services.worker import update_plugin as update_plugin_task
    update_plugin_task.apply_async(kwargs={"plugin_id": plugin_id}, ignore_result=True)
    return ApiResponse(message="Plugin update queued")


@router.get("/{plugin_id}/capabilities", response_model=ApiResponse)
def get_plugin_capabilities(
    plugin_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    plugin = db_session.exec(select(Plugin).where(Plugin.id == plugin_id)).first()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")

    caches = db_session.exec(
        select(PluginCapabilityCache).where(PluginCapabilityCache.plugin_id == plugin_id)
    ).all()

    return ApiResponse(
        message="Capabilities retrieved",
        data={
            "capabilities": [
                {"capability": c.capability, "last_fetched_at": c.last_fetched_at.isoformat()}
                for c in caches
            ]
        },
    )


@router.post("/{plugin_id}/capabilities/{capability}/refresh", response_model=ApiResponse)
def refresh_capability(
    plugin_id: int,
    capability: str,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    require_admin(user_info)

    plugin = db_session.exec(select(Plugin).where(Plugin.id == plugin_id)).first()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")

    client = IntegrationClient(db_session)
    try:
        data = client.get_capability(plugin, capability)
        return ApiResponse(message="Capability refreshed", data=data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
