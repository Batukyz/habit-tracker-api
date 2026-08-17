"""add habit is_archived

Revision ID: 6fc0bada1870
Revises: 5d6f8ee23e80
Create Date: 2026-08-17 14:40:50.293494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fc0bada1870'
down_revision: Union[str, Sequence[str], None] = '5d6f8ee23e80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add as NOT NULL with a server-side default so existing rows backfill to False,
    # then drop the server default to match the model (which only sets a client-side default).
    # batch_alter_table is required for SQLite, which can't ALTER COLUMN directly.
    with op.batch_alter_table('habits') as batch_op:
        batch_op.add_column(
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table('habits') as batch_op:
        batch_op.alter_column('is_archived', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('habits') as batch_op:
        batch_op.drop_column('is_archived')
