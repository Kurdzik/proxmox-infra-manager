"""Add SSH credentials to platform_config for Terraform provider

Revision ID: 006
Revises: 005
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("platform_config", sa.Column("ssh_username", sa.String(), nullable=True))
    op.add_column("platform_config", sa.Column("encrypted_ssh_password", sa.String(), nullable=True))


def downgrade():
    op.drop_column("platform_config", "encrypted_ssh_password")
    op.drop_column("platform_config", "ssh_username")
