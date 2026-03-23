"""add average_unit_cost to inventory item

Revision ID: f08a9b0c1d2e
Revises: ff7a8b9c0d1e
Create Date: 2026-03-09 19:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f08a9b0c1d2e"
down_revision = "ff7a8b9c0d1e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventory_item", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "average_unit_cost",
                sa.Float(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade():
    with op.batch_alter_table("inventory_item", schema=None) as batch_op:
        batch_op.drop_column("average_unit_cost")
