"""Add DHCP metadata to tenant_vnets

Revision ID: 008
Revises: 007
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tenant_vnets", sa.Column("gateway", sa.String(), nullable=True))
    op.add_column("tenant_vnets", sa.Column("dhcp_start", sa.String(), nullable=True))
    op.add_column("tenant_vnets", sa.Column("dhcp_end", sa.String(), nullable=True))
    op.create_index("ix_tenant_vnets_subnet_unique", "tenant_vnets", ["subnet"], unique=True)


def downgrade():
    op.drop_index("ix_tenant_vnets_subnet_unique", table_name="tenant_vnets")
    op.drop_column("tenant_vnets", "dhcp_end")
    op.drop_column("tenant_vnets", "dhcp_start")
    op.drop_column("tenant_vnets", "gateway")
