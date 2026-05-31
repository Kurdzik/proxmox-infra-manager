"""Add cpu_count to proxmox_nodes

Revision ID: 002
Revises: 001
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('proxmox_nodes', sa.Column('cpu_count', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('proxmox_nodes', 'cpu_count')
