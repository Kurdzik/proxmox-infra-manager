import time
from typing import Optional

from src.proxmox.base import BaseProxmoxAdapter, ProxmoxAPIError
from src.proxmox.credentials import ProxmoxCredentials


class ProxmoxVE8Adapter(BaseProxmoxAdapter):
    """Proxmox VE 8.x REST API adapter."""

    def __init__(self, credentials: ProxmoxCredentials) -> None:
        super().__init__(credentials)

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def list_nodes(self) -> list[dict]:
        return self._request("GET", "/nodes")

    def get_node_status(self, node: str) -> dict:
        return self._request("GET", f"/nodes/{node}/status")

    # ------------------------------------------------------------------
    # VMs (QEMU)
    # ------------------------------------------------------------------

    def list_vms(self, node: str) -> list[dict]:
        return self._request("GET", f"/nodes/{node}/qemu")

    def create_vm(self, node: str, vmid: int, config: dict) -> dict:
        return self._request("POST", f"/nodes/{node}/qemu", json={"vmid": vmid, **config})

    def delete_vm(self, node: str, vmid: int) -> dict:
        return self._request("DELETE", f"/nodes/{node}/qemu/{vmid}")

    def start_vm(self, node: str, vmid: int) -> dict:
        return self._request("POST", f"/nodes/{node}/qemu/{vmid}/status/start")

    def stop_vm(self, node: str, vmid: int) -> dict:
        return self._request("POST", f"/nodes/{node}/qemu/{vmid}/status/stop")

    def get_task_status(self, node: str, upid: str) -> dict:
        return self._request("GET", f"/nodes/{node}/tasks/{upid}/status")

    def exec_vm(self, node: str, vmid: int, command: list[str]) -> dict:
        """Execute via QEMU guest agent (requires qemu-guest-agent installed in VM)."""
        return self._request(
            "POST",
            f"/nodes/{node}/qemu/{vmid}/agent/exec",
            json={"command": command},
        )

    def get_vm_ip(self, node: str, vmid: int) -> Optional[str]:
        """Return the first non-loopback IPv4 address via QEMU guest agent, or None."""
        interfaces = self._request("GET", f"/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces")
        if not isinstance(interfaces, list):
            interfaces = interfaces.get("result", []) if isinstance(interfaces, dict) else []
        for iface in interfaces:
            if iface.get("name") == "lo":
                continue
            for addr in iface.get("ip-addresses", []):
                if addr.get("ip-address-type") == "ipv4":
                    ip = addr.get("ip-address", "")
                    if not ip.startswith("127."):
                        return ip
        return None

    def get_vm_status(self, node: str, vmid: int) -> str:
        """Return VM power state (running/stopped/paused) without requiring the QEMU guest agent."""
        data = self._request("GET", f"/nodes/{node}/qemu/{vmid}/status/current")
        return data.get("status", "stopped")

    def get_vm_config(self, node: str, vmid: int) -> dict:
        """Return the full configuration of a QEMU VM."""
        return self._request("GET", f"/nodes/{node}/qemu/{vmid}/config")

    def get_vm_mac(self, node: str, vmid: int) -> Optional[str]:
        """Return the MAC address of net0 for a QEMU VM, or None."""
        config = self.get_vm_config(node, vmid)
        # net0 field looks like "virtio=BC:24:11:AA:BB:CC,bridge=vnabc123"
        net0 = config.get("net0", "")
        for part in net0.split(","):
            if "=" in part:
                k, _, v = part.partition("=")
                if k.lower() in ("virtio", "e1000", "vmxnet3", "rtl8139"):
                    return v.upper()
        return None

    def get_vm_ip_from_ipam(self, vmid: int) -> Optional[str]:
        """Return the IPv4 address registered in Proxmox IPAM for the given vmid, or None.

        Queries GET /cluster/sdn/ips which returns all IPAM-tracked addresses.
        Each entry has 'vmid' and 'ip' (CIDR form, e.g. '10.100.1.50/24').
        Works without the QEMU guest agent — relies on dnsmasq registering the
        lease in the Proxmox internal IPAM when the VM picks up a DHCP address.
        """
        try:
            entries = self._request("GET", "/cluster/sdn/ips")
        except Exception:
            return None
        if not isinstance(entries, list):
            return None
        for entry in entries:
            if entry.get("vmid") == vmid:
                cidr = entry.get("ip", "")
                ip = cidr.split("/")[0]
                if ip and not ip.startswith("127."):
                    return ip
        return None

    # ------------------------------------------------------------------
    # LXC Containers
    # ------------------------------------------------------------------

    def list_cts(self, node: str) -> list[dict]:
        return self._request("GET", f"/nodes/{node}/lxc")

    def create_ct(self, node: str, vmid: int, config: dict) -> dict:
        return self._request("POST", f"/nodes/{node}/lxc", json={"vmid": vmid, **config})

    def delete_ct(self, node: str, vmid: int) -> dict:
        return self._request("DELETE", f"/nodes/{node}/lxc/{vmid}")

    def start_ct(self, node: str, vmid: int) -> dict:
        return self._request("POST", f"/nodes/{node}/lxc/{vmid}/status/start")

    def stop_ct(self, node: str, vmid: int) -> dict:
        return self._request("POST", f"/nodes/{node}/lxc/{vmid}/status/stop")

    def exec_ct(self, node: str, vmid: int, command: list[str]) -> dict:
        return self._request(
            "POST",
            f"/nodes/{node}/lxc/{vmid}/exec",
            json={"command": command},
        )

    def get_ct_ip(self, node: str, vmid: int) -> Optional[str]:
        """Return the first non-loopback IPv4 address from LXC interfaces, or None."""
        interfaces = self._request("GET", f"/nodes/{node}/lxc/{vmid}/interfaces")
        if not isinstance(interfaces, list):
            return None
        for iface in interfaces:
            if iface.get("name") == "lo":
                continue
            inet = iface.get("inet", "")
            if inet:
                ip = inet.split("/")[0]
                if not ip.startswith("127."):
                    return ip
        return None

    # ------------------------------------------------------------------
    # Firewall
    # ------------------------------------------------------------------

    def _firewall_path(self, scope: str, node: Optional[str], vmid: Optional[int]) -> str:
        if scope == "cluster":
            return "/cluster/firewall/rules"
        if scope == "node":
            return f"/nodes/{node}/firewall/rules"
        if scope == "vm":
            return f"/nodes/{node}/qemu/{vmid}/firewall/rules"
        if scope == "ct":
            return f"/nodes/{node}/lxc/{vmid}/firewall/rules"
        raise ValueError(f"Unknown firewall scope: {scope}")

    def list_firewall_rules(
        self, scope: str, node: Optional[str] = None, vmid: Optional[int] = None
    ) -> list[dict]:
        return self._request("GET", self._firewall_path(scope, node, vmid))

    def add_firewall_rule(
        self, scope: str, rule: dict, node: Optional[str] = None, vmid: Optional[int] = None
    ) -> dict:
        return self._request("POST", self._firewall_path(scope, node, vmid), json=rule)

    def delete_firewall_rule(
        self, scope: str, pos: int, node: Optional[str] = None, vmid: Optional[int] = None
    ) -> None:
        path = self._firewall_path(scope, node, vmid).rstrip("rules") + f"rules/{pos}"
        self._request("DELETE", path)

    def update_firewall_rule(
        self,
        scope: str,
        pos: int,
        rule: dict,
        node: Optional[str] = None,
        vmid: Optional[int] = None,
    ) -> dict:
        path = self._firewall_path(scope, node, vmid).rstrip("rules") + f"rules/{pos}"
        return self._request("PUT", path, json=rule)

    # ------------------------------------------------------------------
    # SDN / VNets
    # ------------------------------------------------------------------

    def list_vnets(self) -> list[dict]:
        return self._request("GET", "/cluster/sdn/vnets")

    def get_sdn_zone(self, zone: str) -> dict:
        return self._request("GET", f"/cluster/sdn/zones/{zone}")

    def list_sdn_zones(self) -> list[dict]:
        return self._request("GET", "/cluster/sdn/zones")

    def create_sdn_zone(
        self,
        zone: str,
        zone_type: str = "simple",
        dhcp: Optional[str] = None,
        ipam: Optional[str] = None,
        nodes: Optional[str] = None,
    ) -> dict:
        payload = {"zone": zone, "type": zone_type}
        if dhcp is not None:
            payload["dhcp"] = dhcp
        if ipam is not None:
            payload["ipam"] = ipam
        if nodes is not None:
            payload["nodes"] = nodes
        return self._request("POST", "/cluster/sdn/zones", json=payload)

    def update_sdn_zone(self, zone: str, config: dict) -> dict:
        return self._request("PUT", f"/cluster/sdn/zones/{zone}", json=config)

    def create_vnet(self, vnet_id: str, zone: str, tag: Optional[int] = None) -> dict:
        payload = {"vnet": vnet_id, "zone": zone}
        if tag is not None:
            payload["tag"] = tag
        return self._request("POST", "/cluster/sdn/vnets", json=payload)

    def get_vnet(self, vnet_id: str) -> dict:
        return self._request("GET", f"/cluster/sdn/vnets/{vnet_id}")

    def delete_vnet(self, vnet_id: str) -> None:
        self._request("DELETE", f"/cluster/sdn/vnets/{vnet_id}")

    def list_sdn_subnets(self, vnet_id: str) -> list[dict]:
        return self._request("GET", f"/cluster/sdn/vnets/{vnet_id}/subnets")

    def create_sdn_subnet(
        self,
        vnet_id: str,
        subnet: str,
        gateway: str,
        dhcp_start: str,
        dhcp_end: str,
        snat: bool = True,
    ) -> dict:
        return self._request(
            "POST",
            f"/cluster/sdn/vnets/{vnet_id}/subnets",
            json={
                "type": "subnet",
                "subnet": subnet,
                "gateway": gateway,
                "snat": int(snat),
                "dhcp-range": [f"start-address={dhcp_start},end-address={dhcp_end}"],
            },
        )

    def update_sdn_subnet(self, vnet_id: str, subnet_id: str, config: dict) -> dict:
        return self._request(
            "PUT",
            f"/cluster/sdn/vnets/{vnet_id}/subnets/{subnet_id}",
            json=config,
        )

    def apply_sdn(self) -> dict | str:
        return self._request("PUT", "/cluster/sdn")

    def get_task_log(self, node: str, upid: str) -> list[dict]:
        return self._request("GET", f"/nodes/{node}/tasks/{upid}/log")

    def list_node_network(self, node: str) -> list[dict]:
        return self._request("GET", f"/nodes/{node}/network")

    def list_node_sdn_zone_content(self, node: str, zone: str) -> list[dict]:
        return self._request("GET", f"/nodes/{node}/sdn/zones/{zone}/content")

    def assign_vnet_to_ct(
        self,
        node: str,
        vmid: int,
        vnet_id: str,
        interface: str = "eth0",
    ) -> None:
        self._request(
            "PUT",
            f"/nodes/{node}/lxc/{vmid}/config",
            json={interface: f"name={interface},bridge={vnet_id}"},
        )

    def assign_vnet_to_vm(
        self,
        node: str,
        vmid: int,
        vnet_id: str,
        interface: str = "net0",
    ) -> None:
        self._request(
            "PUT",
            f"/nodes/{node}/qemu/{vmid}/config",
            json={interface: f"virtio,bridge={vnet_id}"},
        )

    # ------------------------------------------------------------------
    # DNS (SDN DNS — stable in PVE 8.x)
    # ------------------------------------------------------------------

    def list_dns_entries(self, zone: str) -> list[dict]:
        return self._request("GET", f"/cluster/sdn/dns/{zone}/records")

    def add_dns_entry(self, zone: str, hostname: str, ip: str, record_type: str = "A") -> None:
        self._request(
            "POST",
            f"/cluster/sdn/dns/{zone}/records",
            json={"name": hostname, "content": ip, "type": record_type},
        )

    def delete_dns_entry(self, zone: str, hostname: str) -> None:
        self._request("DELETE", f"/cluster/sdn/dns/{zone}/records/{hostname}")

    # ------------------------------------------------------------------
    # VM config update
    # ------------------------------------------------------------------

    def update_vm_config(self, node: str, vmid: int, config: dict) -> dict:
        return self._request("PUT", f"/nodes/{node}/qemu/{vmid}/config", json=config)

    def resize_disk(self, node: str, vmid: int, disk: str, size: str) -> dict:
        """Resize a VM disk. size is absolute, e.g. '20G'."""
        return self._request(
            "PUT",
            f"/nodes/{node}/qemu/{vmid}/resize",
            json={"disk": disk, "size": size},
        )

    # ------------------------------------------------------------------
    # Storage / ISO management
    # ------------------------------------------------------------------

    def get_storage_info(self, storage_id: str) -> dict:
        return self._request("GET", f"/storage/{storage_id}")

    def list_storage_content(
        self,
        node: str,
        storage: str,
        content_type: str = "iso",
    ) -> list[dict]:
        return self._request(
            "GET",
            f"/nodes/{node}/storage/{storage}/content",
            params={"content": content_type},
        )

    def download_iso(self, node: str, storage: str, url: str, filename: str) -> str:
        result = self._request(
            "POST",
            f"/nodes/{node}/storage/{storage}/download-url",
            json={"url": url, "filename": filename, "content": "iso"},
        )
        # Proxmox returns the raw UPID string as data
        return result if isinstance(result, str) else str(result)

    def wait_for_task(
        self,
        node: str,
        upid: str,
        poll_interval: int = 5,
        timeout: int = 900,
    ) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self._request("GET", f"/nodes/{node}/tasks/{upid}/status")
            if status.get("status") == "stopped":
                exit_status = status.get("exitstatus", "")
                if exit_status != "OK":
                    raise ProxmoxAPIError(500, f"Task {upid} failed: {exit_status}")
                return
            time.sleep(poll_interval)
        raise TimeoutError(f"Proxmox task {upid} did not complete within {timeout}s")
