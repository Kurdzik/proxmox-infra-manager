import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    username: str = Field(unique=True, index=True)
    password: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    token: str = Field(
        unique=True,
        index=True,
        default_factory=lambda: f"ust-{str(uuid.uuid4()).replace('-', '')}",
    )
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Platform config (single-row, enforced by singleton=True unique constraint)
# ---------------------------------------------------------------------------

class PlatformConfig(SQLModel, table=True):
    __tablename__ = "platform_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    singleton: bool = Field(default=True, unique=True)
    is_initialized: bool = Field(default=False)
    proxmox_url: Optional[str] = None
    proxmox_version: Optional[str] = None   # "7.4", "8.2", etc.
    token_id: Optional[str] = None          # e.g. root@pam!infra-manager
    encrypted_token_secret: Optional[str] = None
    verify_ssl: bool = Field(default=False)
    ssh_username: Optional[str] = None     # SSH user for Terraform provider (e.g. root)
    encrypted_ssh_password: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Cluster state (global, not tenant-scoped)
# ---------------------------------------------------------------------------

class ProxmoxNode(SQLModel, table=True):
    __tablename__ = "proxmox_nodes"

    id: Optional[int] = Field(default=None, primary_key=True)
    node_name: str = Field(index=True, unique=True)
    status: str = Field(default="unknown")   # "online", "offline", "unknown"
    cpu_count: Optional[int] = None
    cpu_usage: Optional[float] = None
    memory_total: Optional[int] = None
    memory_used: Optional[int] = None
    disk_total: Optional[int] = None
    disk_used: Optional[int] = None
    uptime: Optional[int] = None
    last_synced_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Tenant network isolation
# ---------------------------------------------------------------------------

class TenantVNet(SQLModel, table=True):
    __tablename__ = "tenant_vnets"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True, unique=True)
    vnet_id: str = Field(unique=True)    # e.g. "vnet-a1b2c3"
    zone: str
    vlan_tag: Optional[int] = None
    subnet: Optional[str] = None         # e.g. "10.100.5.0/24"
    created_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# VM provisioning
# ---------------------------------------------------------------------------

class VMTemplate(SQLModel, table=True):
    __tablename__ = "vm_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    name: str
    cores: int
    memory_mb: int
    disk_gb: int
    os_image: str           # Proxmox storage path or ISO URL
    image_type: str = Field(default="iso")  # "iso" or "cloud-image"
    network_model: str = Field(default="virtio")
    # Cloud-init fields (used when image_type == "cloud-image")
    cloud_init_user: Optional[str] = None         # default login user, e.g. "ubuntu"
    cloud_init_ssh_keys: Optional[str] = None     # newline-separated public keys
    cloud_init_user_data: Optional[str] = None    # Jinja2 YAML template override
    extra_config: Optional[str] = None   # JSON blob for additional Proxmox params
    created_at: datetime = Field(default_factory=datetime.now)


class VM(SQLModel, table=True):
    __tablename__ = "vms"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    vmid: int = Field(index=True)
    node_name: str
    name: str
    status: str = Field(default="stopped")  # "running", "stopped", "provisioning", "error"
    cpu_cores: Optional[int] = None
    memory_mb: Optional[int] = None
    disk_gb: Optional[int] = None
    ip_address: Optional[str] = None
    cloud_init_user: Optional[str] = None
    template_id: Optional[int] = Field(default=None, foreign_key="vm_templates.id")
    task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class TerraformWorkspace(SQLModel, table=True):
    __tablename__ = "terraform_workspaces"

    id: Optional[int] = Field(default=None, primary_key=True)
    vm_id: int = Field(index=True, foreign_key="vms.id")
    tenant_id: str = Field(index=True)
    rendered_config: str
    terraform_state: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class VMSSHKey(SQLModel, table=True):
    __tablename__ = "vm_ssh_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    vm_id: int = Field(index=True, foreign_key="vms.id")
    tenant_id: str = Field(index=True)
    public_key: str
    private_key_encrypted: str
    key_type: str = Field(default="ed25519")
    created_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Docker image allowlist (global, platform-managed overrides)
# ---------------------------------------------------------------------------

class AllowedImage(SQLModel, table=True):
    __tablename__ = "allowed_images"

    id: Optional[int] = Field(default=None, primary_key=True)
    image_name: str = Field(index=True)
    tag_policy: str = Field(default="any")   # "specific", "semver", "any"
    allowed_tags: Optional[str] = None       # JSON list; null means all tags allowed
    description: Optional[str] = None
    added_by_tenant_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Plugin system (global)
# ---------------------------------------------------------------------------

class Plugin(SQLModel, table=True):
    __tablename__ = "plugins"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    repo_url: str
    encrypted_auth_token: Optional[str] = None  # AES-GCM encrypted
    plugin_dir: str                               # absolute path inside plugins_volume
    compose_file: str
    base_url: str                                 # http://{container}:{port}
    status: str = Field(default="installing")     # "installing", "running", "stopped", "failed", "unreachable"
    capabilities: str = Field(default="[]")       # JSON list of capability names
    version: Optional[str] = None
    installed_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PluginCapabilityCache(SQLModel, table=True):
    __tablename__ = "plugin_capability_cache"

    id: Optional[int] = Field(default=None, primary_key=True)
    plugin_id: int = Field(foreign_key="plugins.id")
    capability: str
    cached_data: str    # JSON blob of last successful response
    last_fetched_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Docker services (per-tenant)
# ---------------------------------------------------------------------------

class DockerService(SQLModel, table=True):
    __tablename__ = "docker_services"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    name: str
    image_name: str
    image_tag: str
    target_vmid: int
    target_type: str    # "vm" or "ct"
    node_name: str
    container_id: Optional[str] = None  # Docker container ID
    internal_port: int
    external_port: Optional[int] = None
    status: str = Field(default="deploying")  # "deploying", "running", "stopped", "error"
    dns_entry_id: Optional[int] = Field(default=None, foreign_key="dns_entries.id")
    nginx_config_id: Optional[int] = Field(default=None, foreign_key="nginx_configs.id")
    task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Firewall rules (per-tenant)
# ---------------------------------------------------------------------------

class FirewallRule(SQLModel, table=True):
    __tablename__ = "firewall_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    scope: str          # "cluster", "node", "vm", "ct"
    node_name: Optional[str] = None
    vmid: Optional[int] = None
    pos: Optional[int] = None
    action: str         # "ACCEPT", "DROP", "REJECT"
    type: str           # "in", "out", "forward"
    proto: Optional[str] = None
    dport: Optional[str] = None
    sport: Optional[str] = None
    source: Optional[str] = None
    dest: Optional[str] = None
    comment: Optional[str] = None
    enable: bool = Field(default=True)
    platform_managed: bool = Field(default=True)
    proxmox_synced: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# DNS entries (per-tenant)
# ---------------------------------------------------------------------------

class DNSEntry(SQLModel, table=True):
    __tablename__ = "dns_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    hostname: str
    ip_address: str
    record_type: str = Field(default="A")
    zone: str
    proxmox_synced: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Nginx configs (per-tenant)
# ---------------------------------------------------------------------------

class NginxConfig(SQLModel, table=True):
    __tablename__ = "nginx_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    service_name: str
    proxy_type: str         # "http" or "stream"
    server_name: str        # DNS name, e.g. "myservice.tenant-a.internal"
    upstream_ip: str
    upstream_port: int
    listen_port: Optional[int] = None   # stream proxy only
    config_filename: str
    rendered_config: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Logging + tenant settings
# ---------------------------------------------------------------------------

class Logs(SQLModel, table=True):
    __tablename__ = "logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    service_name: str = Field(index=True)
    log: str
    timestamp: datetime = Field(default_factory=datetime.now)


class TenantLogSettings(SQLModel, table=True):
    __tablename__ = "tenant_log_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(unique=True, index=True)
    log_retention_period_d: int = Field(default=30)
    log_size: int = Field(default=1_000_000)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
