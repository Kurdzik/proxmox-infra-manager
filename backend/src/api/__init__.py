from fastapi import APIRouter, Depends

from src.api.init import router as init_router
from src.api.users import router as users_router
from src.api.nodes import router as nodes_router
from src.api.vms import router as vms_router
from src.api.containers import router as containers_router
from src.api.docker import router as docker_router
from src.api.plugins import router as plugins_router
from src.api.images import router as images_router
from src.api.firewall import router as firewall_router
from src.api.dns import router as dns_router
from src.api.services import router as services_router
from src.middleware import check_token

# Public router — check_token still runs so request.state is always populated,
# but login/register/init paths are in excluded_paths so no token is enforced there.
public_router = APIRouter(prefix="/api/v1", dependencies=[Depends(check_token)])
public_router.include_router(init_router)
public_router.include_router(users_router)

# Protected router — requires session token
api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(check_token)])
api_router.include_router(nodes_router)
api_router.include_router(vms_router)
api_router.include_router(containers_router)
api_router.include_router(docker_router)
api_router.include_router(plugins_router)
api_router.include_router(images_router)
api_router.include_router(firewall_router)
api_router.include_router(dns_router)
api_router.include_router(services_router)

__all__ = ["api_router", "public_router"]
