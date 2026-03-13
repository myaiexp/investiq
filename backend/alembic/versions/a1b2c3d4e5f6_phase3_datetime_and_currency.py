"""phase3 datetime and currency

Revision ID: a1b2c3d4e5f6
Revises: 00e98610f5a0
Create Date: 2026-03-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '00e98610f5a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: Date→DateTime(tz) for ohlcv_data and indicator_data, add currency to indices."""
    # PostgreSQL implicitly converts Date→Timestamp by assuming 00:00:00
    op.alter_column(
        'ohlcv_data', 'date',
        existing_type=sa.Date(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using='date::timestamptz',
    )
    op.alter_column(
        'indicator_data', 'date',
        existing_type=sa.Date(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using='date::timestamptz',
    )
    op.add_column('indices', sa.Column('currency', sa.String(length=3), nullable=True))


def downgrade() -> None:
    """Downgrade: revert DateTime→Date, drop currency."""
    op.drop_column('indices', 'currency')
    op.alter_column(
        'indicator_data', 'date',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.Date(),
        existing_nullable=False,
        postgresql_using='date::date',
    )
    op.alter_column(
        'ohlcv_data', 'date',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.Date(),
        existing_nullable=False,
        postgresql_using='date::date',
    )
