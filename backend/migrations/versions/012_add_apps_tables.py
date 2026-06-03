"""Add apps tables and seed initial catalog

Revision ID: 012
Revises: 011
Create Date: 2026-06-03
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # --- app_catalog_entries -------------------------------------------------
    op.create_table(
        "app_catalog_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("default_port", sa.Integer(), nullable=False),
        sa.Column("port_range_start", sa.Integer(), nullable=False),
        sa.Column("port_range_end", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # --- app_versions --------------------------------------------------------
    op.create_table(
        "app_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_entry_id", sa.Integer(), sa.ForeignKey("app_catalog_entries.id"), nullable=False, index=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # --- app_playbooks -------------------------------------------------------
    op.create_table(
        "app_playbooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_entry_id", sa.Integer(), sa.ForeignKey("app_catalog_entries.id"), nullable=False, index=True),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("app_versions.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("playbook_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- app_instances -------------------------------------------------------
    op.create_table(
        "app_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("catalog_entry_id", sa.Integer(), sa.ForeignKey("app_catalog_entries.id"), nullable=False, index=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("vm_id", sa.Integer(), sa.ForeignKey("vms.id"), nullable=True),
        sa.Column("node_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="provisioning"),
        sa.Column("internal_port", sa.Integer(), nullable=False),
        sa.Column("external_port", sa.Integer(), nullable=True),
        sa.Column("nginx_config_id", sa.Integer(), sa.ForeignKey("nginx_configs.id"), nullable=True),
        sa.Column("connection_credentials", sa.Text(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- Seed PostgreSQL catalog entry + versions + playbook -----------------
    _seed_postgres(op)


def _seed_postgres(op):
    from datetime import datetime
    now = datetime.now()

    catalog_table = sa.table(
        "app_catalog_entries",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("description", sa.String),
        sa.column("default_port", sa.Integer),
        sa.column("port_range_start", sa.Integer),
        sa.column("port_range_end", sa.Integer),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(catalog_table, [
        {
            "id": 1,
            "name": "PostgreSQL",
            "slug": "postgres",
            "description": "Open source relational database",
            "default_port": 5432,
            "port_range_start": 54000,
            "port_range_end": 54999,
            "created_at": now,
        }
    ])

    versions_table = sa.table(
        "app_versions",
        sa.column("id", sa.Integer),
        sa.column("catalog_entry_id", sa.Integer),
        sa.column("version", sa.String),
        sa.column("is_latest", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(versions_table, [
        {"id": 1, "catalog_entry_id": 1, "version": "15", "is_latest": False, "created_at": now},
        {"id": 2, "catalog_entry_id": 1, "version": "16", "is_latest": False, "created_at": now},
        {"id": 3, "catalog_entry_id": 1, "version": "17", "is_latest": True,  "created_at": now},
    ])

    # Load playbook template from source file
    playbook_path = Path(__file__).parent.parent.parent / "src" / "playbooks" / "postgres.yml.j2"
    playbook_content = playbook_path.read_text()

    playbooks_table = sa.table(
        "app_playbooks",
        sa.column("id", sa.Integer),
        sa.column("catalog_entry_id", sa.Integer),
        sa.column("version_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("playbook_content", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(playbooks_table, [
        {
            "id": 1,
            "catalog_entry_id": 1,
            "version_id": None,  # applies to all versions
            "name": "Install PostgreSQL",
            "description": "Installs and configures PostgreSQL with a remote-access user",
            "playbook_content": playbook_content,
            "created_at": now,
            "updated_at": now,
        }
    ])


def downgrade():
    op.drop_table("app_instances")
    op.drop_table("app_playbooks")
    op.drop_table("app_versions")
    op.drop_table("app_catalog_entries")
