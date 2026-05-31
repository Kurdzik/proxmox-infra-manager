from src.proxmox.v8 import ProxmoxVE8Adapter
from src.proxmox.credentials import ProxmoxCredentials


class ProxmoxVE7Adapter(ProxmoxVE8Adapter):
    """Proxmox VE 7.x REST API adapter.

    Most endpoints are identical to 8.x. The main difference is SDN DNS,
    which is not stable in 7.x and raises NotImplementedError.
    """

    def __init__(self, credentials: ProxmoxCredentials) -> None:
        super().__init__(credentials)

    # SDN DNS API is not stable in PVE 7.x
    def list_dns_entries(self, zone: str) -> list[dict]:
        raise NotImplementedError(
            "DNS management via SDN API requires Proxmox VE 8.x. "
            "Use the node-level DNS configuration for PVE 7.x."
        )

    def add_dns_entry(self, zone: str, hostname: str, ip: str, record_type: str = "A") -> None:
        raise NotImplementedError(
            "DNS management via SDN API requires Proxmox VE 8.x."
        )

    def delete_dns_entry(self, zone: str, hostname: str) -> None:
        raise NotImplementedError(
            "DNS management via SDN API requires Proxmox VE 8.x."
        )
