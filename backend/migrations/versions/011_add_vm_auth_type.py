"""Add auth_type to vms

Revision ID: 011
Revises: 010
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vms", sa.Column("auth_type", sa.String(), nullable=False, server_default="ssh_key"))


def downgrade():
    op.drop_column("vms", "auth_type")
