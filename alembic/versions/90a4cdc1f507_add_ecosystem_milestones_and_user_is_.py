"""add ecosystem milestones and user is_admin

Revision ID: 90a4cdc1f507
Revises: 3b651e57f71c
Create Date: 2026-08-27 00:08:06.518052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90a4cdc1f507'
down_revision: Union[str, Sequence[str], None] = '3b651e57f71c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ecosystem_milestones_table = sa.table(
    'ecosystem_milestones',
    sa.column('threshold', sa.Integer),
    sa.column('stage_key', sa.String),
    sa.column('name', sa.String),
    sa.column('description', sa.String),
)

DEFAULT_MILESTONES = [
    {'threshold': 0, 'stage_key': 'empty', 'name': 'Boş Toprak', 'description': 'Henüz bir seri başlatmadın.'},
    {'threshold': 1, 'stage_key': 'seed', 'name': 'Tohum', 'description': 'İlk adımı attın.'},
    {'threshold': 3, 'stage_key': 'sprout', 'name': 'Filiz', 'description': 'Küçük bir filiz toprağı yardı.'},
    {'threshold': 7, 'stage_key': 'young_plant', 'name': 'Genç Bitki', 'description': 'Bitki kök salmaya başladı.'},
    {'threshold': 14, 'stage_key': 'growing', 'name': 'Büyüyen Bahçe', 'description': 'Yapraklar ve ilk çiçekler belirdi.'},
    {'threshold': 30, 'stage_key': 'garden', 'name': 'İlk Bahçe', 'description': 'Küçük bir yaşam alanı oluştu.'},
    {'threshold': 60, 'stage_key': 'thriving', 'name': 'Gelişen Ekosistem', 'description': 'Çiçekler ve küçük canlılar katıldı.'},
    {'threshold': 100, 'stage_key': 'mature', 'name': 'Olgun Bahçe', 'description': 'Ağaçlar büyüdü, ekosistem zenginleşti.'},
    {'threshold': 365, 'stage_key': 'ancient', 'name': 'Kadim Bahçe', 'description': 'Uzun soluklu başarının nişanesi.'},
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ecosystem_milestones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('stage_key', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('threshold'),
    )
    op.create_index(op.f('ix_ecosystem_milestones_id'), 'ecosystem_milestones', ['id'], unique=False)
    op.bulk_insert(ecosystem_milestones_table, DEFAULT_MILESTONES)

    # Add as NOT NULL with a server-side default so existing rows backfill to False,
    # then drop the server default to match the model (which only sets a client-side default).
    # batch_alter_table is required for SQLite, which can't ALTER COLUMN directly.
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('is_admin', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('is_admin')
    op.drop_index(op.f('ix_ecosystem_milestones_id'), table_name='ecosystem_milestones')
    op.drop_table('ecosystem_milestones')
