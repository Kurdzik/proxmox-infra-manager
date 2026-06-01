"""Add console_password_encrypted to vms

Revision ID: 010
Revises: 009
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vms", sa.Column("console_password_encrypted", sa.String(), nullable=True))


def downgrade():
    op.drop_column("vms", "console_password_encrypted")
