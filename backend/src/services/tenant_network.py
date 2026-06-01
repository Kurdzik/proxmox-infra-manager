import hashlib
import ipaddress
import os
import re
import time
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.crypto import decrypt_str
from src.models import PlatformConfig, TenantVNet
from src.proxmox import (
    BaseProxmoxAdapter,
    ProxmoxAdapterFactory,
    ProxmoxAPIError,
    ProxmoxCredentials,
)

DEFAULT_TENANT_SDN_ZONE = os.environ.get("TENANT_SDN_ZONE", "default")
DEFAULT_TENANT_SUBNET_POOL = os.environ.get("TENANT_SUBNET_POOL", "10.100.0.0/16")
DEFAULT_DHCP_START_OFFSET = int(os.environ.get("TENANT_DHCP_START_OFFSET", "100"))
DEFAULT_DHCP_END_OFFSET = int(os.environ.get("TENANT_DHCP_END_OFFSET", "199"))
DEFAULT_SDN_BRIDGE_WAIT_SECONDS = int(os.environ.get("TENANT_SDN_BRIDGE_WAIT_SECONDS", "300"))
DEFAULT_SDN_BRIDGE_POLL_INTERVAL = int(os.environ.get("TENANT_SDN_BRIDGE_POLL_INTERVAL", "5"))
DEFAULT_TENANT_SDN_SNAT = os.environ.get("TENANT_SDN_SNAT", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
PROXMOX_VNET_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,7}$")


class TenantNetworkError(RuntimeError):
    pass


@dataclass(frozen=True)
class TenantNetworkSettings:
    subnet: str
    gateway: str
    dhcp_start: str
    dhcp_end: str


def get_platform_adapter(db_session: Session) -> BaseProxmoxAdapter:
    config = db_session.exec(select(PlatformConfig)).first()
    if not config or not config.is_initialized:
        raise TenantNetworkError("Platform not initialized")
    token_secret = decrypt_str(config.encrypted_token_secret)
    credentials = ProxmoxCredentials(
        url=config.proxmox_url,
        token_id=config.token_id,
        token_secret=token_secret,
        verify_ssl=config.verify_ssl,
    )
    return ProxmoxAdapterFactory.create(config.proxmox_version, credentials)


def allocate_next_tenant_subnet(
    used_subnets: Iterable[str | None],
    pool_cidr: str = DEFAULT_TENANT_SUBNET_POOL,
) -> str:
    pool = ipaddress.ip_network(pool_cidr)
    if not isinstance(pool, ipaddress.IPv4Network):
        raise TenantNetworkError("Tenant subnet pool must be an IPv4 network")
    if pool.prefixlen > 24:
        raise TenantNetworkError("Tenant subnet pool must be large enough to allocate /24 networks")

    used = [
        ipaddress.ip_network(subnet)
        for subnet in used_subnets
        if subnet
    ]
    for subnet in pool.subnets(new_prefix=24):
        if not any(subnet.overlaps(existing) for existing in used):
            return str(subnet)

    raise TenantNetworkError(f"No free /24 tenant subnets remain in {pool_cidr}")


def derive_tenant_network_settings(subnet: str) -> TenantNetworkSettings:
    network = ipaddress.ip_network(subnet)
    if not isinstance(network, ipaddress.IPv4Network):
        raise TenantNetworkError("Tenant VNet DHCP currently supports IPv4 subnets only")
    if network.num_addresses <= DEFAULT_DHCP_END_OFFSET:
        raise TenantNetworkError(
            f"Tenant subnet {subnet} is too small for DHCP offset {DEFAULT_DHCP_END_OFFSET}"
        )

    return TenantNetworkSettings(
        subnet=str(network),
        gateway=str(network.network_address + 1),
        dhcp_start=str(network.network_address + DEFAULT_DHCP_START_OFFSET),
        dhcp_end=str(network.network_address + DEFAULT_DHCP_END_OFFSET),
    )


def ensure_tenant_vnet(
    db_session: Session,
    adapter: BaseProxmoxAdapter,
    tenant_id: str,
    *,
    target_node: Optional[str] = None,
    commit: bool = False,
) -> TenantVNet:
    db_changed = False
    # Fetch the default VNet for this tenant (may be None if none yet).
    vnet = db_session.exec(
        select(TenantVNet).where(TenantVNet.tenant_id == tenant_id, TenantVNet.is_default == True)  # noqa: E712
    ).first()
    if not vnet:
        vnet = TenantVNet(
            tenant_id=tenant_id,
            vnet_id=_next_vnet_id(db_session, tenant_id),
            zone=DEFAULT_TENANT_SDN_ZONE,
            name="Default",
            is_default=True,
        )
        db_session.add(vnet)
        db_changed = True
    elif not _valid_vnet_id(vnet.vnet_id):
        vnet.vnet_id = _next_vnet_id(db_session, tenant_id)
        db_changed = True

    if not vnet.subnet:
        used_subnets = [row.subnet for row in db_session.exec(select(TenantVNet)).all()]
        vnet.subnet = allocate_next_tenant_subnet(used_subnets)
        db_changed = True

    settings = derive_tenant_network_settings(vnet.subnet)
    if vnet.subnet != settings.subnet:
        vnet.subnet = settings.subnet
        db_changed = True
    if not vnet.gateway:
        vnet.gateway = settings.gateway
        db_changed = True
    if not vnet.dhcp_start:
        vnet.dhcp_start = settings.dhcp_start
        db_changed = True
    if not vnet.dhcp_end:
        vnet.dhcp_end = settings.dhcp_end
        db_changed = True
    db_session.add(vnet)
    db_session.flush()

    changed = db_changed
    changed |= _ensure_sdn_zone(adapter, vnet.zone, target_node)
    changed |= _ensure_sdn_vnet(adapter, vnet)
    changed |= _ensure_sdn_subnet(adapter, vnet)

    if changed:
        task = adapter.apply_sdn()
        _wait_for_sdn_apply(adapter, task)

    if target_node and not _wait_for_node_vnet(adapter, target_node, vnet.zone, vnet.vnet_id):
        task = adapter.apply_sdn()
        _wait_for_sdn_apply(adapter, task)
        if not _wait_for_node_vnet(adapter, target_node, vnet.zone, vnet.vnet_id):
            status_text = _node_sdn_vnet_status_text(adapter, target_node, vnet.zone, vnet.vnet_id)
            status_suffix = f" ({status_text})" if status_text else ""
            raise TenantNetworkError(
                f"SDN VNet {vnet.vnet_id} is not active on {target_node}{status_suffix}. "
                "Check Proxmox SDN apply logs and ensure dnsmasq is installed for "
                "automatic DHCP."
            )

    if commit:
        try:
            db_session.commit()
        except IntegrityError as exc:
            db_session.rollback()
            raise TenantNetworkError(
                "Tenant VNet allocation conflicted; retry provisioning"
            ) from exc

    return vnet


def ensure_vnet_on_node(
    db_session: Session,
    adapter: BaseProxmoxAdapter,
    vnet: TenantVNet,
    target_node: str,
) -> None:
    """Ensure a specific (possibly non-default) VNet's SDN bridge is active on target_node.

    Handles SDN apply + bridge wait without touching subnet allocation or DHCP settings
    (those were set at creation time). Used by the worker for non-default VNets.
    """
    changed = False
    changed |= _ensure_sdn_zone(adapter, vnet.zone, target_node)
    changed |= _ensure_sdn_vnet(adapter, vnet)
    changed |= _ensure_sdn_subnet(adapter, vnet)

    if changed:
        task = adapter.apply_sdn()
        _wait_for_sdn_apply(adapter, task)

    if not _wait_for_node_vnet(adapter, target_node, vnet.zone, vnet.vnet_id):
        task = adapter.apply_sdn()
        _wait_for_sdn_apply(adapter, task)
        if not _wait_for_node_vnet(adapter, target_node, vnet.zone, vnet.vnet_id):
            status_text = _node_sdn_vnet_status_text(adapter, target_node, vnet.zone, vnet.vnet_id)
            status_suffix = f" ({status_text})" if status_text else ""
            raise TenantNetworkError(
                f"SDN VNet {vnet.vnet_id} is not active on {target_node}{status_suffix}. "
                "Check Proxmox SDN apply logs and ensure dnsmasq is installed."
            )


def get_vm_ip_from_leases(
    node_host: str,
    mac: str,
    ssh_username: str,
    ssh_password: str,
) -> Optional[str]:
    """Return the IP for *mac* by reading the dnsmasq lease files on the Proxmox node via SSH.

    Proxmox SDN creates per-VNet dnsmasq lease files under /var/lib/misc/ or
    /var/run/dnsmasq-*.leases depending on the version.  We read both paths
    and return the first match.

    Returns None on any error or if the MAC is not found.
    """
    import asyncio
    import asyncssh  # type: ignore[import-untyped]

    mac_norm = mac.upper()

    async def _read_leases() -> Optional[str]:
        try:
            async with asyncssh.connect(
                node_host,
                username=ssh_username,
                password=ssh_password,
                known_hosts=None,
                connect_timeout=10,
                preferred_auth="password,keyboard-interactive",
            ) as conn:
                # Try both common dnsmasq lease file locations used by Proxmox SDN
                for cmd in (
                    "cat /var/lib/misc/dnsmasq.leases 2>/dev/null || true",
                    "cat /var/run/dnsmasq-*.leases 2>/dev/null || true",
                    "find /var/lib/dnsmasq -name '*.leases' -exec cat {} + 2>/dev/null || true",
                ):
                    result = await conn.run(cmd, check=False)
                    output = result.stdout or ""
                    for line in output.splitlines():
                        # dnsmasq lease line: <expiry> <mac> <ip> <hostname> <clientid>
                        parts = line.split()
                        if len(parts) >= 3 and parts[1].upper() == mac_norm:
                            ip = parts[2]
                            if ip and not ip.startswith("0.") and not ip.startswith("127."):
                                return ip
        except Exception:
            pass
        return None

    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(_read_leases())
    except Exception:
        return None
    finally:
        try:
            loop.close()
        except Exception:
            pass


def allocate_static_ip(db_session: Session, vnet: "TenantVNet") -> str:
    """Allocate the next free static IP from the VNet's address range.

    Scans all VMs already on this VNet (by ip_address) and returns the lowest
    IP in [dhcp_start, dhcp_end] that is not yet in use.  Call inside the
    tenant provision advisory lock so concurrent provisions don't race.
    """
    from src.models import VM  # local import to avoid circular dependency at module level

    start = ipaddress.ip_address(vnet.dhcp_start)
    end = ipaddress.ip_address(vnet.dhcp_end)

    used_ips: set[ipaddress.IPv4Address] = set()
    for vm in db_session.exec(select(VM).where(VM.network_id == vnet.id)).all():
        if vm.ip_address:
            try:
                used_ips.add(ipaddress.ip_address(vm.ip_address))  # type: ignore[arg-type]
            except ValueError:
                pass

    current = start
    while current <= end:
        if current not in used_ips:
            return str(current)
        current += 1

    raise TenantNetworkError(
        f"No free IPs available in VNet {vnet.vnet_id} range {vnet.dhcp_start}–{vnet.dhcp_end}"
    )


def create_named_vnet(
    db_session: Session,
    adapter: BaseProxmoxAdapter,
    tenant_id: str,
    name: str,
) -> TenantVNet:
    """Create an additional named VNet for a tenant with auto-allocated subnet.

    Unlike ensure_tenant_vnet(), this always creates a new VNet (is_default=False)
    and raises TenantNetworkError on any failure.
    """
    import secrets

    # Generate a unique Proxmox-compatible VNet ID (e.g. "vnf3a2b1")
    for _ in range(20):
        suffix = secrets.token_hex(3)  # 6 hex chars
        vnet_id = f"vn{suffix}"
        if not db_session.exec(select(TenantVNet).where(TenantVNet.vnet_id == vnet_id)).first():
            break
    else:
        raise TenantNetworkError(f"Unable to allocate a unique VNet ID for tenant {tenant_id}")

    used_subnets = [row.subnet for row in db_session.exec(select(TenantVNet)).all()]
    subnet = allocate_next_tenant_subnet(used_subnets)
    settings = derive_tenant_network_settings(subnet)

    vnet = TenantVNet(
        tenant_id=tenant_id,
        vnet_id=vnet_id,
        zone=DEFAULT_TENANT_SDN_ZONE,
        subnet=settings.subnet,
        gateway=settings.gateway,
        dhcp_start=settings.dhcp_start,
        dhcp_end=settings.dhcp_end,
        name=name,
        is_default=False,
    )
    db_session.add(vnet)
    db_session.flush()

    _ensure_sdn_zone(adapter, vnet.zone, target_node=None)
    _ensure_sdn_vnet(adapter, vnet)
    _ensure_sdn_subnet(adapter, vnet)

    task = adapter.apply_sdn()
    _wait_for_sdn_apply(adapter, task)

    try:
        db_session.commit()
    except IntegrityError as exc:
        db_session.rollback()
        raise TenantNetworkError("VNet allocation conflicted; retry") from exc

    return vnet


def _next_vnet_id(db_session: Session, tenant_id: str) -> str:
    candidates = [
        f"vn{tenant_id[:6]}",
        f"vn{tenant_id[6:12]}",
        f"vn{tenant_id[12:18]}",
        f"vn{tenant_id[-6:]}",
    ]
    for attempt in range(16):
        digest = hashlib.sha1(f"{tenant_id}:{attempt}".encode()).hexdigest()[:6]
        candidates.append(f"vn{digest}")

    for vnet_id in candidates:
        existing = db_session.exec(select(TenantVNet).where(TenantVNet.vnet_id == vnet_id)).first()
        if not existing:
            return vnet_id
    raise TenantNetworkError(f"Unable to allocate unique VNet ID for tenant {tenant_id}")


def _valid_vnet_id(vnet_id: str) -> bool:
    return bool(PROXMOX_VNET_ID_RE.fullmatch(vnet_id))


def _ensure_sdn_zone(
    adapter: BaseProxmoxAdapter,
    zone: str,
    target_node: Optional[str],
) -> bool:
    try:
        current = adapter.get_sdn_zone(zone)
    except ProxmoxAPIError as exc:
        if not _sdn_zone_missing(adapter, zone, exc):
            raise TenantNetworkError(f"Failed to inspect SDN zone {zone}: {exc.detail}") from exc
        _create_sdn_zone(adapter, zone, target_node)
        return True

    if current.get("type") not in (None, "simple"):
        raise TenantNetworkError(
            f"Tenant SDN zone {zone} exists with unsupported type {current.get('type')}"
        )

    updates = {}
    if current.get("dhcp") != "dnsmasq":
        updates["dhcp"] = "dnsmasq"
    if current.get("ipam") != "pve":
        updates["ipam"] = "pve"
    current_nodes = _parse_zone_nodes(current.get("nodes"))
    if target_node and target_node not in current_nodes:
        current_nodes.add(target_node)
        updates["nodes"] = _format_zone_nodes(current_nodes)
    if updates:
        try:
            adapter.update_sdn_zone(zone, updates)
        except ProxmoxAPIError as exc:
            raise TenantNetworkError(
                f"Failed to enable DHCP/IPAM on SDN zone {zone}: {exc.detail}"
            ) from exc
        return True
    return False


def _create_sdn_zone(
    adapter: BaseProxmoxAdapter,
    zone: str,
    target_node: Optional[str],
) -> None:
    try:
        adapter.create_sdn_zone(
            zone=zone,
            zone_type="simple",
            dhcp="dnsmasq",
            ipam="pve",
            nodes=target_node,
        )
    except ProxmoxAPIError as exc:
        if not _already_exists(exc):
            raise TenantNetworkError(f"Failed to create SDN zone {zone}: {exc.detail}") from exc


def _ensure_sdn_vnet(adapter: BaseProxmoxAdapter, vnet: TenantVNet) -> bool:
    try:
        current = adapter.get_vnet(vnet.vnet_id)
    except ProxmoxAPIError as exc:
        if not _sdn_vnet_missing(adapter, vnet.vnet_id, exc):
            raise TenantNetworkError(
                f"Failed to inspect VNet {vnet.vnet_id}: {exc.detail}"
            ) from exc
        _create_sdn_vnet(adapter, vnet)
        return True

    current_zone = current.get("zone")
    if current_zone and current_zone != vnet.zone:
        raise TenantNetworkError(
            f"VNet {vnet.vnet_id} already belongs to zone {current_zone}, expected {vnet.zone}"
        )
    return False


def _create_sdn_vnet(adapter: BaseProxmoxAdapter, vnet: TenantVNet) -> None:
    try:
        adapter.create_vnet(vnet_id=vnet.vnet_id, zone=vnet.zone, tag=vnet.vlan_tag)
    except ProxmoxAPIError as exc:
        if not _already_exists(exc):
            raise TenantNetworkError(f"Failed to create VNet {vnet.vnet_id}: {exc.detail}") from exc


def _ensure_sdn_subnet(adapter: BaseProxmoxAdapter, vnet: TenantVNet) -> bool:
    try:
        subnets = adapter.list_sdn_subnets(vnet.vnet_id)
    except ProxmoxAPIError as exc:
        raise TenantNetworkError(
            f"Failed to list subnets for VNet {vnet.vnet_id}: {exc.detail}"
        ) from exc

    subnet = _matching_subnet(subnets, vnet.subnet)
    if not subnet:
        _create_sdn_subnet(adapter, vnet)
        return True

    if _subnet_has_expected_config(subnet, vnet):
        return False

    subnet_id = subnet.get("id") or _derive_subnet_id(vnet.zone, vnet.subnet)
    try:
        adapter.update_sdn_subnet(
            vnet.vnet_id,
            subnet_id,
            _subnet_payload(vnet),
        )
    except ProxmoxAPIError as exc:
        raise TenantNetworkError(
            f"Failed to repair subnet {vnet.subnet} on VNet {vnet.vnet_id}: {exc.detail}"
        ) from exc
    return True


def _create_sdn_subnet(adapter: BaseProxmoxAdapter, vnet: TenantVNet) -> None:
    try:
        adapter.create_sdn_subnet(
            vnet_id=vnet.vnet_id,
            subnet=vnet.subnet,
            gateway=vnet.gateway,
            dhcp_start=vnet.dhcp_start,
            dhcp_end=vnet.dhcp_end,
            snat=DEFAULT_TENANT_SDN_SNAT,
        )
    except ProxmoxAPIError as exc:
        if not _already_exists(exc):
            raise TenantNetworkError(
                f"Failed to create subnet {vnet.subnet} on VNet {vnet.vnet_id}: {exc.detail}"
            ) from exc


def _subnet_payload(vnet: TenantVNet) -> dict:
    return {
        "type": "subnet",
        "subnet": vnet.subnet,
        "gateway": vnet.gateway,
        "snat": int(DEFAULT_TENANT_SDN_SNAT),
        "dhcp-range": [f"start-address={vnet.dhcp_start},end-address={vnet.dhcp_end}"],
    }


def _matching_subnet(subnets: list[dict], cidr: Optional[str]) -> Optional[dict]:
    for subnet in subnets:
        if _subnet_cidr(subnet) == cidr:
            return subnet
    return None


def _subnet_cidr(subnet: dict) -> Optional[str]:
    if subnet.get("cidr"):
        return subnet["cidr"]
    if subnet.get("subnet"):
        return subnet["subnet"]
    if subnet.get("network") and subnet.get("mask"):
        return f"{subnet['network']}/{subnet['mask']}"
    return None


def _subnet_has_expected_config(subnet: dict, vnet: TenantVNet) -> bool:
    if subnet.get("gateway") != vnet.gateway:
        return False
    if DEFAULT_TENANT_SDN_SNAT and subnet.get("snat") not in (1, "1", True):
        return False
    return _dhcp_range_matches(subnet.get("dhcp-range"), vnet.dhcp_start, vnet.dhcp_end)


def _dhcp_range_matches(value: object, dhcp_start: str, dhcp_end: str) -> bool:
    expected = f"start-address={dhcp_start},end-address={dhcp_end}"
    if value == expected:
        return True
    if isinstance(value, list):
        for item in value:
            if item == expected:
                return True
            if (
                isinstance(item, dict)
                and item.get("start-address") == dhcp_start
                and item.get("end-address") == dhcp_end
            ):
                return True
    return False


def _derive_subnet_id(zone: str, cidr: str) -> str:
    network = ipaddress.ip_network(cidr)
    return f"{zone}-{network.network_address}-{network.prefixlen}"


def _parse_zone_nodes(value: object) -> set[str]:
    if not value:
        return set()
    if isinstance(value, list):
        return {str(item) for item in value if item}
    return {item for item in re.split(r"[,\s;]+", str(value)) if item}


def _format_zone_nodes(nodes: set[str]) -> str:
    return ",".join(sorted(nodes))


def _node_sdn_vnet_status(
    adapter: BaseProxmoxAdapter,
    node: str,
    zone: str,
    vnet_id: str,
) -> Optional[tuple[Optional[str], Optional[str]]]:
    try:
        content = adapter.list_node_sdn_zone_content(node, zone)
    except ProxmoxAPIError as exc:
        if exc.status_code in {404, 501}:
            return None
        raise TenantNetworkError(
            f"Failed to inspect SDN zone {zone} content on {node}: {exc.detail}"
        ) from exc

    for item in content:
        if item.get("vnet") == vnet_id or item.get("id") == vnet_id or item.get("name") == vnet_id:
            return item.get("status"), item.get("statusmsg")
    return None


def _node_sdn_vnet_status_text(
    adapter: BaseProxmoxAdapter,
    node: str,
    zone: str,
    vnet_id: str,
) -> Optional[str]:
    status = _node_sdn_vnet_status(adapter, node, zone, vnet_id)
    if not status:
        return None
    state, message = status
    parts = [part for part in (state, message) if part]
    return ", ".join(parts) if parts else None


def _node_has_vnet(adapter: BaseProxmoxAdapter, node: str, zone: str, vnet_id: str) -> bool:
    status = _node_sdn_vnet_status(adapter, node, zone, vnet_id)
    if status is not None:
        return status[0] == "available"

    try:
        return any(item.get("iface") == vnet_id for item in adapter.list_node_network(node))
    except ProxmoxAPIError as exc:
        raise TenantNetworkError(
            f"Failed to inspect network interfaces on {node}: {exc.detail}"
        ) from exc


def _wait_for_node_vnet(
    adapter: BaseProxmoxAdapter,
    node: str,
    zone: str,
    vnet_id: str,
) -> bool:
    deadline = time.time() + DEFAULT_SDN_BRIDGE_WAIT_SECONDS
    while True:
        if _node_has_vnet(adapter, node, zone, vnet_id):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(DEFAULT_SDN_BRIDGE_POLL_INTERVAL)


def _sdn_zone_missing(adapter: BaseProxmoxAdapter, zone: str, exc: ProxmoxAPIError) -> bool:
    if exc.status_code == 404:
        return True
    if exc.status_code != 500:
        return False
    try:
        zones = adapter.list_sdn_zones()
    except ProxmoxAPIError:
        return False
    return not any(item.get("zone") == zone or item.get("id") == zone for item in zones)


def _sdn_vnet_missing(adapter: BaseProxmoxAdapter, vnet_id: str, exc: ProxmoxAPIError) -> bool:
    if exc.status_code == 404:
        return True
    if exc.status_code != 500:
        return False
    try:
        vnets = adapter.list_vnets()
    except ProxmoxAPIError:
        return False
    return not any(item.get("vnet") == vnet_id or item.get("id") == vnet_id for item in vnets)


def _wait_for_sdn_apply(adapter: BaseProxmoxAdapter, task: dict | str) -> None:
    upid = task if isinstance(task, str) else task.get("upid") or task.get("data")
    if not isinstance(upid, str) or not upid.startswith("UPID:"):
        return

    parts = upid.split(":")
    if len(parts) < 2 or not parts[1]:
        return
    node = parts[1]
    adapter.wait_for_task(node, upid, poll_interval=2, timeout=180)
    log_lines = _task_log_text(adapter, node, upid)
    if "missing 'dnsmasq' package" in log_lines:
        raise TenantNetworkError(
            "Proxmox SDN automatic DHCP requires the dnsmasq package on the target "
            "node. Install it on Proxmox with `apt install dnsmasq` and disable the "
            "default service with `systemctl disable --now dnsmasq`, then retry."
        )
    if "failed: exit code" in log_lines or "proxy handler failed" in log_lines:
        raise TenantNetworkError(f"Proxmox SDN apply completed with errors: {log_lines}")


def _task_log_text(adapter: BaseProxmoxAdapter, node: str, upid: str) -> str:
    try:
        log = adapter.get_task_log(node, upid)
    except ProxmoxAPIError:
        return ""
    return "\n".join(str(item.get("t", "")) for item in log)


def _already_exists(exc: ProxmoxAPIError) -> bool:
    detail = exc.detail.lower()
    return exc.status_code in {400, 409} and (
        "already exists" in detail
        or "already defined" in detail
        or "duplicate" in detail
    )
