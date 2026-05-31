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
    token_secret: str
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
    # Provide either template_id (existing template) OR image_id+os_image (direct from image list)
    template_id: Optional[int] = None
    image_id: Optional[str] = None   # e.g. "ubuntu-2404"
    os_image: Optional[str] = None   # e.g. "local:iso/ubuntu-24.04.1-live-server-amd64.iso"


# ---------------------------------------------------------------------------
# Containers (LXC)
# ---------------------------------------------------------------------------

class CreateCTTemplateRequest(BaseModel):
    name: str
    cores: int
    memory_mb: int
    rootfs_gb: int
    os_template_url: str
    extra_config: Optional[str] = None


class ProvisionCTRequest(BaseModel):
    template_id: int
    node_name: str
    ct_name: str


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
