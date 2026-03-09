"""add usage_type and is_active to inventory_item

Revision ID: f3a9b1c7d2e4
Revises: e1b4c7d9a2f6
Create Date: 2026-03-09 16:25:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f3a9b1c7d2e4"
down_revision = "e1b4c7d9a2f6"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _check_constraint_exists(inspector, table_name, constraint_name):
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inventory_item" not in inspector.get_table_names():
        return

    if not _column_exists(inspector, "inventory_item", "usage_type"):
        with op.batch_alter_table("inventory_item", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "usage_type",
                    sa.String(length=30),
                    nullable=False,
                    server_default="mixed",
                )
            )

    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "inventory_item", "is_active"):
        with op.batch_alter_table("inventory_item", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "is_active",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                )
            )

    inspector = sa.inspect(bind)
    if not _check_constraint_exists(
        inspector,
        "inventory_item",
        "ck_inventory_item_usage_type",
    ):
        with op.batch_alter_table("inventory_item", schema=None) as batch_op:
            batch_op.create_check_constraint(
                "ck_inventory_item_usage_type",
                "usage_type IN ('sale_direct', 'production_input', 'mixed')",
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inventory_item" not in inspector.get_table_names():
        return

    if _check_constraint_exists(
        inspector, "inventory_item", "ck_inventory_item_usage_type"
    ):
        with op.batch_alter_table("inventory_item", schema=None) as batch_op:
            batch_op.drop_constraint("ck_inventory_item_usage_type", type_="check")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "inventory_item", "is_active"):
        with op.batch_alter_table("inventory_item", schema=None) as batch_op:
            batch_op.drop_column("is_active")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "inventory_item", "usage_type"):
        with op.batch_alter_table("inventory_item", schema=None) as batch_op:
            batch_op.drop_column("usage_type")
