"""Add cpu_cores, memory_mb, disk_gb to vms and containers

Revision ID: 003
Revises: 002
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vms', sa.Column('cpu_cores', sa.Integer(), nullable=True))
    op.add_column('vms', sa.Column('memory_mb', sa.Integer(), nullable=True))
    op.add_column('vms', sa.Column('disk_gb', sa.Integer(), nullable=True))

    op.add_column('containers', sa.Column('cpu_cores', sa.Integer(), nullable=True))
    op.add_column('containers', sa.Column('memory_mb', sa.Integer(), nullable=True))
    op.add_column('containers', sa.Column('disk_gb', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('vms', 'cpu_cores')
    op.drop_column('vms', 'memory_mb')
    op.drop_column('vms', 'disk_gb')

    op.drop_column('containers', 'cpu_cores')
    op.drop_column('containers', 'memory_mb')
    op.drop_column('containers', 'disk_gb')
