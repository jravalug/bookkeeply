"""add lot metadata to inventory movement

Revision ID: fe6f7a8b9c0d
Revises: fd5e6f7a8b9c
Create Date: 2026-03-09 19:22:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fe6f7a8b9c0d"
down_revision = "fd5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lot_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("lot_unit", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("lot_conversion_factor", sa.Float(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.drop_column("lot_conversion_factor")
        batch_op.drop_column("lot_unit")
        batch_op.drop_column("lot_date")
