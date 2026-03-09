"""add wip subproduct fields and product inventory flags

Revision ID: f9c1d2e3a4b5
Revises: f8a1b2c3d4e5
Create Date: 2026-03-09 19:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f9c1d2e3a4b5"
down_revision = "f8a1b2c3d4e5"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _check_exists(inspector, table_name, check_name):
    return any(
        check.get("name") == check_name
        for check in inspector.get_check_constraints(table_name)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "product" in inspector.get_table_names():
        if not _column_exists(inspector, "product", "can_be_subproduct"):
            with op.batch_alter_table("product", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "can_be_subproduct",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    )
                )

        inspector = sa.inspect(bind)
        if not _column_exists(inspector, "product", "goes_to_sales_floor"):
            with op.batch_alter_table("product", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "goes_to_sales_floor",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    )
                )

    inspector = sa.inspect(bind)
    if "inventory_wip_balance" in inspector.get_table_names():
        if not _column_exists(
            inspector, "inventory_wip_balance", "produced_product_id"
        ):
            with op.batch_alter_table("inventory_wip_balance", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column("produced_product_id", sa.Integer(), nullable=True)
                )
                batch_op.create_foreign_key(
                    "fk_inventory_wip_balance_produced_product_id",
                    "product",
                    ["produced_product_id"],
                    ["id"],
                )

        inspector = sa.inspect(bind)
        if not _column_exists(inspector, "inventory_wip_balance", "can_be_subproduct"):
            with op.batch_alter_table("inventory_wip_balance", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "can_be_subproduct",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    )
                )

        inspector = sa.inspect(bind)
        if not _column_exists(inspector, "inventory_wip_balance", "finished_location"):
            with op.batch_alter_table("inventory_wip_balance", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "finished_location",
                        sa.String(length=30),
                        nullable=False,
                        server_default="finished_goods",
                    )
                )

        inspector = sa.inspect(bind)
        if not _check_exists(
            inspector,
            "inventory_wip_balance",
            "ck_inventory_wip_balance_finished_location",
        ):
            with op.batch_alter_table("inventory_wip_balance", schema=None) as batch_op:
                batch_op.create_check_constraint(
                    "ck_inventory_wip_balance_finished_location",
                    "finished_location IN ('finished_goods', 'sales_floor')",
                )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inventory_wip_balance" in inspector.get_table_names():
        if _check_exists(
            inspector,
            "inventory_wip_balance",
            "ck_inventory_wip_balance_finished_location",
        ):
            with op.batch_alter_table("inventory_wip_balance", schema=None) as batch_op:
                batch_op.drop_constraint(
                    "ck_inventory_wip_balance_finished_location",
                    type_="check",
                )

        inspector = sa.inspect(bind)
        if _column_exists(inspector, "inventory_wip_balance", "finished_location"):
            with op.batch_alter_table("inventory_wip_balance", schema=None) as batch_op:
                batch_op.drop_column("finished_location")

        inspector = sa.inspect(bind)
        if _column_exists(inspector, "inventory_wip_balance", "can_be_subproduct"):
            with op.batch_alter_table("inventory_wip_balance", schema=None) as batch_op:
                batch_op.drop_column("can_be_subproduct")

        inspector = sa.inspect(bind)
        if _column_exists(inspector, "inventory_wip_balance", "produced_product_id"):
            with op.batch_alter_table("inventory_wip_balance", schema=None) as batch_op:
                batch_op.drop_constraint(
                    "fk_inventory_wip_balance_produced_product_id",
                    type_="foreignkey",
                )
                batch_op.drop_column("produced_product_id")

    inspector = sa.inspect(bind)
    if "product" in inspector.get_table_names():
        if _column_exists(inspector, "product", "goes_to_sales_floor"):
            with op.batch_alter_table("product", schema=None) as batch_op:
                batch_op.drop_column("goes_to_sales_floor")

        inspector = sa.inspect(bind)
        if _column_exists(inspector, "product", "can_be_subproduct"):
            with op.batch_alter_table("product", schema=None) as batch_op:
                batch_op.drop_column("can_be_subproduct")
