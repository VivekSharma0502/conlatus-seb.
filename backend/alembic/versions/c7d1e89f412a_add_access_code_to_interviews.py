"""Add access_code and lifecycle tracking to interviews

Revision ID: c7d1e89f412a
Revises: 'bac96f606f7d'
Create Date: 2026-10-29 00:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d1e89f412a'
down_revision: Union[str, None] = 'bac96f606f7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('interviews', schema=None) as batch_op:
        batch_op.add_column(sa.Column('access_code', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('access_code_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('access_code_used', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('access_code_used_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_interviews_access_code'), ['access_code'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('interviews', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_interviews_access_code'))
        batch_op.drop_column('access_code_used_at')
        batch_op.drop_column('access_code_used')
        batch_op.drop_column('access_code_expires_at')
        batch_op.drop_column('access_code')

