"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("username", sa.String, nullable=False, unique=True, index=True),
        sa.Column("password", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String, nullable=False, unique=True, index=True),
        sa.Column("ip_address", sa.String, nullable=True),
        sa.Column("user_agent", sa.String, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "platform_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("singleton", sa.Boolean, nullable=False, unique=True, server_default="true"),
        sa.Column("is_initialized", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("proxmox_url", sa.String, nullable=True),
        sa.Column("proxmox_version", sa.String, nullable=True),
        sa.Column("token_id", sa.String, nullable=True),
        sa.Column("encrypted_token_secret", sa.String, nullable=True),
        sa.Column("verify_ssl", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "proxmox_nodes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("node_name", sa.String, nullable=False, unique=True, index=True),
        sa.Column("status", sa.String, nullable=False, server_default="unknown"),
        sa.Column("cpu_usage", sa.Float, nullable=True),
        sa.Column("memory_total", sa.BigInteger, nullable=True),
        sa.Column("memory_used", sa.BigInteger, nullable=True),
        sa.Column("disk_total", sa.BigInteger, nullable=True),
        sa.Column("disk_used", sa.BigInteger, nullable=True),
        sa.Column("uptime", sa.Integer, nullable=True),
        sa.Column("last_synced_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "tenant_vnets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, unique=True, index=True),
        sa.Column("vnet_id", sa.String, nullable=False, unique=True),
        sa.Column("zone", sa.String, nullable=False),
        sa.Column("vlan_tag", sa.Integer, nullable=True),
        sa.Column("subnet", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "vm_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("cores", sa.Integer, nullable=False),
        sa.Column("memory_mb", sa.Integer, nullable=False),
        sa.Column("disk_gb", sa.Integer, nullable=False),
        sa.Column("os_image", sa.String, nullable=False),
        sa.Column("network_model", sa.String, nullable=False, server_default="virtio"),
        sa.Column("extra_config", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "vms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("vmid", sa.Integer, nullable=False, index=True),
        sa.Column("node_name", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="stopped"),
        sa.Column("ip_address", sa.String, nullable=True),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("vm_templates.id"), nullable=True),
        sa.Column("task_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "ct_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("cores", sa.Integer, nullable=False),
        sa.Column("memory_mb", sa.Integer, nullable=False),
        sa.Column("rootfs_gb", sa.Integer, nullable=False),
        sa.Column("os_template_url", sa.String, nullable=False),
        sa.Column("extra_config", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "containers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("vmid", sa.Integer, nullable=False, index=True),
        sa.Column("node_name", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="stopped"),
        sa.Column("ip_address", sa.String, nullable=True),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("ct_templates.id"), nullable=True),
        sa.Column("task_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "allowed_images",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("image_name", sa.String, nullable=False, index=True),
        sa.Column("tag_policy", sa.String, nullable=False, server_default="any"),
        sa.Column("allowed_tags", sa.Text, nullable=True),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("added_by_tenant_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "plugins",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True, index=True),
        sa.Column("repo_url", sa.String, nullable=False),
        sa.Column("encrypted_auth_token", sa.String, nullable=True),
        sa.Column("plugin_dir", sa.String, nullable=False),
        sa.Column("compose_file", sa.String, nullable=False),
        sa.Column("base_url", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="installing"),
        sa.Column("capabilities", sa.Text, nullable=False, server_default="[]"),
        sa.Column("version", sa.String, nullable=True),
        sa.Column("installed_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "plugin_capability_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plugin_id", sa.Integer, sa.ForeignKey("plugins.id"), nullable=False),
        sa.Column("capability", sa.String, nullable=False),
        sa.Column("cached_data", sa.Text, nullable=False),
        sa.Column("last_fetched_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "dns_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("hostname", sa.String, nullable=False),
        sa.Column("ip_address", sa.String, nullable=False),
        sa.Column("record_type", sa.String, nullable=False, server_default="A"),
        sa.Column("zone", sa.String, nullable=False),
        sa.Column("proxmox_synced", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "nginx_configs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("service_name", sa.String, nullable=False),
        sa.Column("proxy_type", sa.String, nullable=False),
        sa.Column("server_name", sa.String, nullable=False),
        sa.Column("upstream_ip", sa.String, nullable=False),
        sa.Column("upstream_port", sa.Integer, nullable=False),
        sa.Column("listen_port", sa.Integer, nullable=True),
        sa.Column("config_filename", sa.String, nullable=False),
        sa.Column("rendered_config", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "docker_services",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("image_name", sa.String, nullable=False),
        sa.Column("image_tag", sa.String, nullable=False),
        sa.Column("target_vmid", sa.Integer, nullable=False),
        sa.Column("target_type", sa.String, nullable=False),
        sa.Column("node_name", sa.String, nullable=False),
        sa.Column("container_id", sa.String, nullable=True),
        sa.Column("internal_port", sa.Integer, nullable=False),
        sa.Column("external_port", sa.Integer, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="deploying"),
        sa.Column("dns_entry_id", sa.Integer, sa.ForeignKey("dns_entries.id"), nullable=True),
        sa.Column("nginx_config_id", sa.Integer, sa.ForeignKey("nginx_configs.id"), nullable=True),
        sa.Column("task_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "firewall_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column("node_name", sa.String, nullable=True),
        sa.Column("vmid", sa.Integer, nullable=True),
        sa.Column("pos", sa.Integer, nullable=True),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("proto", sa.String, nullable=True),
        sa.Column("dport", sa.String, nullable=True),
        sa.Column("sport", sa.String, nullable=True),
        sa.Column("source", sa.String, nullable=True),
        sa.Column("dest", sa.String, nullable=True),
        sa.Column("comment", sa.String, nullable=True),
        sa.Column("enable", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("platform_managed", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("proxmox_synced", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, index=True),
        sa.Column("service_name", sa.String, nullable=False, index=True),
        sa.Column("log", sa.Text, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
    )

    op.create_table(
        "tenant_log_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String, nullable=False, unique=True, index=True),
        sa.Column("log_retention_period_d", sa.Integer, nullable=False, server_default="30"),
        sa.Column("log_size", sa.Integer, nullable=False, server_default="1000000"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tenant_log_settings")
    op.drop_table("logs")
    op.drop_table("firewall_rules")
    op.drop_table("docker_services")
    op.drop_table("nginx_configs")
    op.drop_table("dns_entries")
    op.drop_table("plugin_capability_cache")
    op.drop_table("plugins")
    op.drop_table("allowed_images")
    op.drop_table("containers")
    op.drop_table("ct_templates")
    op.drop_table("vms")
    op.drop_table("vm_templates")
    op.drop_table("tenant_vnets")
    op.drop_table("proxmox_nodes")
    op.drop_table("platform_config")
    op.drop_table("sessions")
    op.drop_table("users")
