export interface ApiResponse<T = any> {
  message: string;
  data: T;
  status: number;
  detail?: string;
}

// ── Platform ──────────────────────────────────────────────────────────────────

export interface InitStatus {
  is_initialized: boolean;
}

export interface PlatformConfig {
  proxmox_url: string;
  proxmox_version: string;
  verify_ssl: boolean;
}

// ── Nodes ─────────────────────────────────────────────────────────────────────

export interface Node {
  id: number;
  name: string;
  hostname: string;
  cpu_count: number;
  memory_mb: number;
  status: string;
  last_seen_at: string;
}

// ── VMs ───────────────────────────────────────────────────────────────────────

export interface VMTemplate {
  id: number;
  name: string;
  cores: number;
  memory_mb: number;
  disk_gb: number;
  os_image: string;
  network_model: string;
}

export interface VM {
  id: number;
  vmid: number;
  name: string;
  node_name: string;
  status: string;
  cpu_cores: number;
  memory_mb: number;
  disk_gb: number;
  ip_address?: string;
  template_id?: number;
  tenant_id: string;
}

// ── Containers ────────────────────────────────────────────────────────────────

export interface CTTemplate {
  id: number;
  name: string;
  cpu_cores: number;
  memory_mb: number;
  disk_gb: number;
  os_template: string;
}

export interface Container {
  id: number;
  vmid: number;
  name: string;
  node_name: string;
  status: string;
  cpu_cores: number;
  memory_mb: number;
  disk_gb: number;
  ip_address?: string;
  template_id?: number;
  tenant_id: string;
}

// ── Docker ────────────────────────────────────────────────────────────────────

export interface DockerService {
  id: number;
  name: string;
  image_name: string;
  image_tag: string;
  target_vmid: number;
  target_type: "vm" | "ct";
  node_name: string;
  container_id?: string;
  internal_port: number;
  external_port?: number;
  status: string;
  dns_entry_id?: number;
  nginx_config_id?: number;
  tenant_id: string;
  dns?: DNSEntry;
  nginx?: { server_name: string; proxy_type: string };
}

// ── DNS ───────────────────────────────────────────────────────────────────────

export interface DNSEntry {
  id: number;
  hostname: string;
  ip_address: string;
  record_type: string;
  zone?: string;
  tenant_id: string;
}

// ── Firewall ──────────────────────────────────────────────────────────────────

export interface FirewallRule {
  id: number;
  scope: string;
  scope_id?: number;
  action: string;
  direction: string;
  protocol?: string;
  source_ip?: string;
  dest_ip?: string;
  source_port?: string;
  dest_port?: string;
  comment?: string;
  platform_managed: boolean;
  enabled: boolean;
  tenant_id: string;
}

// ── Plugins ───────────────────────────────────────────────────────────────────

export interface Plugin {
  id: number;
  name: string;
  repo_url: string;
  plugin_dir: string;
  base_url: string;
  status: string;
  capabilities: string;
  version?: string;
  installed_at: string;
  updated_at: string;
}

// ── Images ────────────────────────────────────────────────────────────────────

export interface AllowedImage {
  id: number;
  name: string;
  tags: string;
  description?: string;
  source: "local" | "plugin";
}

export interface VmImage {
  id: string;
  name: string;
  description: string;
  os_family: string;
  filename: string;
  url: string;
  size_gb: number;
  available: boolean;
}

// ── Users ─────────────────────────────────────────────────────────────────────

export interface UserInfo {
  username: string;
  tenant_id: string;
  is_admin: boolean;
}
