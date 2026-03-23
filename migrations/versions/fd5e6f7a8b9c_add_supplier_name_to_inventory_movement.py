"""add supplier_name to inventory movement

Revision ID: fd5e6f7a8b9c
Revises: fc4d5e6f7a8b
Create Date: 2026-03-09 19:02:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fd5e6f7a8b9c"
down_revision = "fc4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("supplier_name", sa.String(length=160), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.drop_column("supplier_name")
