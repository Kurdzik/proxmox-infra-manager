import inspect
from typing import Optional

import httpx

from src.proxmox.credentials import ProxmoxCredentials


class ProxmoxAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Proxmox API error {status_code}: {detail}")


class BaseProxmoxAdapter:
    """Abstract base for Proxmox VE REST API adapters. Instantiated per-task, not as singleton."""

    def __init__(self, credentials: ProxmoxCredentials) -> None:
        self.credentials = credentials
        self._base_url = credentials.url.rstrip("/")
        self._headers = {
            "Authorization": f"PVEAPIToken={credentials.token_id}={credentials.token_secret}"
        }

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self._base_url}/api2/json{path}"
        with httpx.Client(verify=self.credentials.verify_ssl, timeout=30) as client:
            response = client.request(method, url, headers=self._headers, **kwargs)
        if response.status_code >= 400:
            raise ProxmoxAPIError(response.status_code, response.text)
        return response.json().get("data", {})

    def _not_implemented(self):
        raise NotImplementedError(
            f"Method {inspect.stack()[1].function} is not implemented for this adapter version"
        )

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def list_nodes(self) -> list[dict]:
        self._not_implemented()

    def get_node_status(self, node: str) -> dict:
        self._not_implemented()

    # ------------------------------------------------------------------
    # VMs (QEMU)
    # ------------------------------------------------------------------

    def list_vms(self, node: str) -> list[dict]:
        self._not_implemented()

    def create_vm(self, node: str, vmid: int, config: dict) -> dict:
        self._not_implemented()

    def delete_vm(self, node: str, vmid: int) -> dict:
        self._not_implemented()

    def start_vm(self, node: str, vmid: int) -> dict:
        self._not_implemented()

    def stop_vm(self, node: str, vmid: int) -> dict:
        self._not_implemented()

    def get_task_status(self, node: str, upid: str) -> dict:
        self._not_implemented()

    def exec_vm(self, node: str, vmid: int, command: list[str]) -> dict:
        """Execute a command inside a QEMU VM via the QEMU guest agent."""
        self._not_implemented()

    # ------------------------------------------------------------------
    # LXC Containers
    # ------------------------------------------------------------------

    def list_cts(self, node: str) -> list[dict]:
        self._not_implemented()

    def create_ct(self, node: str, vmid: int, config: dict) -> dict:
        self._not_implemented()

    def delete_ct(self, node: str, vmid: int) -> dict:
        self._not_implemented()

    def start_ct(self, node: str, vmid: int) -> dict:
        self._not_implemented()

    def stop_ct(self, node: str, vmid: int) -> dict:
        self._not_implemented()

    def exec_ct(self, node: str, vmid: int, command: list[str]) -> dict:
        """Execute a command inside an LXC container."""
        self._not_implemented()

    # ------------------------------------------------------------------
    # Firewall
    # ------------------------------------------------------------------

    def list_firewall_rules(
        self, scope: str, node: Optional[str] = None, vmid: Optional[int] = None
    ) -> list[dict]:
        self._not_implemented()

    def add_firewall_rule(
        self, scope: str, rule: dict, node: Optional[str] = None, vmid: Optional[int] = None
    ) -> dict:
        self._not_implemented()

    def delete_firewall_rule(
        self, scope: str, pos: int, node: Optional[str] = None, vmid: Optional[int] = None
    ) -> None:
        self._not_implemented()

    def update_firewall_rule(
        self,
        scope: str,
        pos: int,
        rule: dict,
        node: Optional[str] = None,
        vmid: Optional[int] = None,
    ) -> dict:
        self._not_implemented()

    # ------------------------------------------------------------------
    # SDN / VNets
    # ------------------------------------------------------------------

    def list_vnets(self) -> list[dict]:
        self._not_implemented()

    def create_vnet(self, vnet_id: str, zone: str, tag: Optional[int] = None) -> dict:
        self._not_implemented()

    def delete_vnet(self, vnet_id: str) -> None:
        self._not_implemented()

    def assign_vnet_to_ct(self, node: str, vmid: int, vnet_id: str, interface: str = "eth0") -> None:
        self._not_implemented()

    def assign_vnet_to_vm(self, node: str, vmid: int, vnet_id: str, interface: str = "net0") -> None:
        self._not_implemented()

    # ------------------------------------------------------------------
    # DNS (SDN DNS — stable in PVE 8.x; limited in 7.x)
    # ------------------------------------------------------------------

    def list_dns_entries(self, zone: str) -> list[dict]:
        self._not_implemented()

    def add_dns_entry(self, zone: str, hostname: str, ip: str, record_type: str = "A") -> None:
        self._not_implemented()

    def delete_dns_entry(self, zone: str, hostname: str) -> None:
        self._not_implemented()

    # ------------------------------------------------------------------
    # Storage / ISO management
    # ------------------------------------------------------------------

    def list_storage_content(self, node: str, storage: str, content_type: str = "iso") -> list[dict]:
        """List files in a storage volume. Returns list of dicts with 'volid', 'size', etc."""
        self._not_implemented()

    def download_iso(self, node: str, storage: str, url: str, filename: str) -> str:
        """Trigger an ISO download via Proxmox download-url API. Returns the UPID task ID."""
        self._not_implemented()

    def wait_for_task(self, node: str, upid: str, poll_interval: int = 5, timeout: int = 900) -> None:
        """Block until a Proxmox task (UPID) completes, raising on failure."""
        self._not_implemented()
