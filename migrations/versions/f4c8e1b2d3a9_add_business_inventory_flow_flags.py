"""add business inventory flow flags

Revision ID: f4c8e1b2d3a9
Revises: f3a9b1c7d2e4
Create Date: 2026-03-09 16:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f4c8e1b2d3a9"
down_revision = "f3a9b1c7d2e4"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "business" not in inspector.get_table_names():
        return

    if not _column_exists(inspector, "business", "inventory_flow_sales_floor_enabled"):
        with op.batch_alter_table("business", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "inventory_flow_sales_floor_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                )
            )

    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "business", "inventory_flow_wip_enabled"):
        with op.batch_alter_table("business", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "inventory_flow_wip_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "business" not in inspector.get_table_names():
        return

    if _column_exists(inspector, "business", "inventory_flow_wip_enabled"):
        with op.batch_alter_table("business", schema=None) as batch_op:
            batch_op.drop_column("inventory_flow_wip_enabled")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "business", "inventory_flow_sales_floor_enabled"):
        with op.batch_alter_table("business", schema=None) as batch_op:
            batch_op.drop_column("inventory_flow_sales_floor_enabled")
