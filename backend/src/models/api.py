from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    message: str
    data: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    detail: str
    request_id: Optional[str] = None


class UserInfo(BaseModel):
    user_id: int
    tenant_id: str
    is_admin: bool = False


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

class InitConfigureRequest(BaseModel):
    proxmox_url: str
    proxmox_version: str    # "7.4", "8.2", etc.
    token_id: str
    token_secret: Optional[str] = None   # omit to keep the existing stored secret
    verify_ssl: bool = False


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ---------------------------------------------------------------------------
# VMs
# ---------------------------------------------------------------------------

class CreateVMTemplateRequest(BaseModel):
    name: str
    cores: int
    memory_mb: int
    disk_gb: int
    os_image: str
    network_model: str = "virtio"
    extra_config: Optional[str] = None


class ProvisionVMRequest(BaseModel):
    node_name: str
    vm_name: str
    image_id: str               # must be a cloud-image type, e.g. "ubuntu-2404-cloud"
    cpu_cores: int = 2
    memory_mb: int = 2048
    disk_gb: int = 20
    cloud_init_user: str = "ubuntu"
    bridge: Optional[str] = None      # explicit Proxmox bridge override (rarely needed)
    network_id: Optional[int] = None  # FK to TenantVNet.id; uses default VNet when omitted
    user_ssh_key_ids: list[int] = []
    auth_type: str = "ssh_key"        # "ssh_key" | "password"
    user_password: Optional[str] = None  # used when auth_type == "password"


# ---------------------------------------------------------------------------
# Networks / VNets
# ---------------------------------------------------------------------------

class VNetResponse(BaseModel):
    id: int
    vnet_id: str
    name: str
    is_default: bool
    subnet: Optional[str]
    gateway: Optional[str]
    dhcp_start: Optional[str]
    dhcp_end: Optional[str]
    vm_count: int
    created_at: datetime


class CreateVNetRequest(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

class DeployDockerServiceRequest(BaseModel):
    target_vmid: int
    target_type: str        # "vm" or "ct"
    node_name: str
    service_name: str
    image_name: str
    image_tag: str
    internal_port: int
    external_port: Optional[int] = None
    proxy_type: str = "http"  # "http" or "stream"
    dns_hostname: Optional[str] = None


# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------

class AddFirewallRuleRequest(BaseModel):
    scope: str
    node_name: Optional[str] = None
    vmid: Optional[int] = None
    action: str
    type: str
    proto: Optional[str] = None
    dport: Optional[str] = None
    sport: Optional[str] = None
    source: Optional[str] = None
    dest: Optional[str] = None
    comment: Optional[str] = None
    enable: bool = True


# ---------------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------------

class AddDNSEntryRequest(BaseModel):
    hostname: str
    ip_address: str
    record_type: str = "A"
    zone: str


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------

class InstallPluginRequest(BaseModel):
    repo_url: str
    auth_token: Optional[str] = None
    env_overrides: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

class AddAllowedImageRequest(BaseModel):
    image_name: str
    tag_policy: str = "any"
    allowed_tags: Optional[list[str]] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------

class ProvisionAppRequest(BaseModel):
    catalog_entry_id: int
    version_id: int
    app_name: str
    node_name: str
    image_id: str
    cpu_cores: int = 2
    memory_mb: int = 2048
    disk_gb: int = 20
    network_id: Optional[int] = None  # FK to TenantVNet.id; null = auto-create isolated VNet
