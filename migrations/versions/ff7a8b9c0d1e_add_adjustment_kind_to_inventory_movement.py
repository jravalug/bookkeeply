"""add adjustment_kind to inventory movement

Revision ID: ff7a8b9c0d1e
Revises: fe6f7a8b9c0d
Create Date: 2026-03-09 19:42:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ff7a8b9c0d1e"
down_revision = "fe6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("adjustment_kind", sa.String(length=20), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_inventory_movement_adjustment_kind"),
            ["adjustment_kind"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_inventory_movement_adjustment_kind"))
        batch_op.drop_column("adjustment_kind")
