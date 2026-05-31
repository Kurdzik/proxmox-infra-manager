from src.proxmox.base import BaseProxmoxAdapter, ProxmoxAPIError
from src.proxmox.credentials import ProxmoxCredentials
from src.proxmox.v7 import ProxmoxVE7Adapter
from src.proxmox.v8 import ProxmoxVE8Adapter


class ProxmoxAdapterFactory:
    _registry = {
        "7": ProxmoxVE7Adapter,
        "8": ProxmoxVE8Adapter,
    }

    @classmethod
    def create(cls, version: str, credentials: ProxmoxCredentials) -> BaseProxmoxAdapter:
        major = version.split(".")[0]
        adapter_cls = cls._registry.get(major)
        if not adapter_cls:
            raise ValueError(
                f"Unsupported Proxmox version: {version}. "
                f"Supported major versions: {list(cls._registry.keys())}"
            )
        return adapter_cls(credentials)


__all__ = [
    "ProxmoxAdapterFactory",
    "BaseProxmoxAdapter",
    "ProxmoxAPIError",
    "ProxmoxCredentials",
    "ProxmoxVE7Adapter",
    "ProxmoxVE8Adapter",
]
