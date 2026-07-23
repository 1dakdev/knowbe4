"""seed skill_dimensions data

Revision ID: e40792bd996d
Revises: b3c4d5aacb7f
Create Date: 2026-07-23 19:55:58.665878

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.seed.skill_dimensions import SKILL_DIMENSIONS

# revision identifiers, used by Alembic.
revision: str = 'e40792bd996d'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5aacb7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

skill_dimensions_table = sa.table(
    "skill_dimensions",
    sa.column("key", sa.String),
    sa.column("name", sa.String),
    sa.column("rubric_description", sa.Text),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(skill_dimensions_table, SKILL_DIMENSIONS)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM skill_dimensions")
