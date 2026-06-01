"""Add terraform workspaces, SSH keys, remove containers/ct_templates

Revision ID: 005
Revises: 004
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("containers")
    op.drop_table("ct_templates")

    op.create_table(
        "terraform_workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vm_id", sa.Integer(), sa.ForeignKey("vms.id"), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("rendered_config", sa.Text(), nullable=False),
        sa.Column("terraform_state", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "vm_ssh_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vm_id", sa.Integer(), sa.ForeignKey("vms.id"), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("private_key_encrypted", sa.Text(), nullable=False),
        sa.Column("key_type", sa.String(), nullable=False, server_default="ed25519"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.add_column("vms", sa.Column("cloud_init_user", sa.String(), nullable=True))


def downgrade():
    op.drop_column("vms", "cloud_init_user")
    op.drop_table("vm_ssh_keys")
    op.drop_table("terraform_workspaces")
    # NOTE: containers and ct_templates are NOT recreated — this migration is irreversible
