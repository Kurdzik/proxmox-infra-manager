"""Replace Ansible postgres playbook with docker-compose template

Revision ID: 013
Revises: 012
Create Date: 2026-06-03
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

_PLAYBOOK_FILE = Path(__file__).parent.parent.parent / "src" / "playbooks" / "postgres.yml.j2"


def upgrade() -> None:
    compose_content = _PLAYBOOK_FILE.read_text()
    op.execute(
        sa.text(
            "UPDATE app_playbooks SET playbook_content = :content, "
            "name = 'PostgreSQL docker-compose', "
            "description = 'Runs postgres:<version> via Docker Compose with a persistent volume' "
            "WHERE catalog_entry_id = 1"
        ).bindparams(content=compose_content)
    )


def downgrade() -> None:
    pass
