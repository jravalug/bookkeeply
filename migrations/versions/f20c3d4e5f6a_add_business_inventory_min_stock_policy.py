"""add business inventory min stock policy

Revision ID: f20c3d4e5f6a
Revises: f19b2c3d4e5f
Create Date: 2026-03-09 20:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f20c3d4e5f6a"
down_revision = "f19b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("business", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "inventory_min_stock_policy",
                sa.String(length=20),
                nullable=False,
                server_default="alert",
            )
        )
        batch_op.create_check_constraint(
            "business_inventory_min_stock_policy_allowed_values",
            "inventory_min_stock_policy IN ('alert', 'block')",
        )


def downgrade():
    with op.batch_alter_table("business", schema=None) as batch_op:
        batch_op.drop_constraint(
            "business_inventory_min_stock_policy_allowed_values",
            type_="check",
        )
        batch_op.drop_column("inventory_min_stock_policy")
