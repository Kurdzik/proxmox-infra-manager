"""Add cloud-init fields to vm_templates

Revision ID: 004
Revises: 003
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vm_templates', sa.Column('image_type', sa.String(), nullable=False, server_default='iso'))
    op.add_column('vm_templates', sa.Column('cloud_init_user', sa.String(), nullable=True))
    op.add_column('vm_templates', sa.Column('cloud_init_ssh_keys', sa.Text(), nullable=True))
    op.add_column('vm_templates', sa.Column('cloud_init_user_data', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('vm_templates', 'image_type')
    op.drop_column('vm_templates', 'cloud_init_user')
    op.drop_column('vm_templates', 'cloud_init_ssh_keys')
    op.drop_column('vm_templates', 'cloud_init_user_data')
