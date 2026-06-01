"""Multi-VNet support per tenant

Revision ID: 009
Revises: 008
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Remove unique index on tenant_vnets.tenant_id so one tenant can have many VNets.
    #    Migration 001 created this as a unique index named "ix_tenant_vnets_tenant_id".
    #    Replace it with a plain (non-unique) index to keep query performance.
    op.drop_index("ix_tenant_vnets_tenant_id", table_name="tenant_vnets")
    op.create_index("ix_tenant_vnets_tenant_id", "tenant_vnets", ["tenant_id"])

    # 2. Add user-visible label and default-flag columns.
    op.add_column("tenant_vnets", sa.Column("name", sa.String(), nullable=False, server_default="Default"))
    op.add_column("tenant_vnets", sa.Column("is_default", sa.Boolean(), nullable=False, server_default="true"))

    # 3. Existing rows are the auto-created tenant defaults — mark them accordingly.
    #    After this one-shot update, new non-default VNets will be inserted with is_default=false.
    op.execute(sa.text("UPDATE tenant_vnets SET is_default = true, name = 'Default'"))

    # 4. Add network_id FK to vms so each VM knows which VNet it lives on.
    op.add_column("vms", sa.Column("network_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_vms_network_id",
        "vms",
        "tenant_vnets",
        ["network_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_vms_network_id", "vms", type_="foreignkey")
    op.drop_column("vms", "network_id")
    op.drop_column("tenant_vnets", "is_default")
    op.drop_column("tenant_vnets", "name")
    op.drop_index("ix_tenant_vnets_tenant_id", table_name="tenant_vnets")
    op.create_index("ix_tenant_vnets_tenant_id", "tenant_vnets", ["tenant_id"], unique=True)
