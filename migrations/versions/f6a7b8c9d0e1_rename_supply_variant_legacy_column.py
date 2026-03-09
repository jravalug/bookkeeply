"""rename legacy supply product_surtido to product_variant

Revision ID: f6a7b8c9d0e1
Revises: f5d2a1b3c4e6
Create Date: 2026-03-09 17:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "f5d2a1b3c4e6"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _unique_exists(inspector, table_name, constraint_name):
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "supply" not in inspector.get_table_names():
        return

    if _column_exists(inspector, "supply", "product_surtido") and not _column_exists(
        inspector, "supply", "product_variant"
    ):
        with op.batch_alter_table("supply", schema=None) as batch_op:
            batch_op.alter_column("product_surtido", new_column_name="product_variant")

    inspector = sa.inspect(bind)
    if _unique_exists(inspector, "supply", "uq_supply_business_product_surtido"):
        with op.batch_alter_table("supply", schema=None) as batch_op:
            batch_op.drop_constraint(
                "uq_supply_business_product_surtido", type_="unique"
            )

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "supply", "product_variant") and not _unique_exists(
        inspector, "supply", "uq_supply_business_product_variant"
    ):
        with op.batch_alter_table("supply", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_supply_business_product_variant",
                ["business_id", "product_variant"],
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "supply" not in inspector.get_table_names():
        return

    if _unique_exists(inspector, "supply", "uq_supply_business_product_variant"):
        with op.batch_alter_table("supply", schema=None) as batch_op:
            batch_op.drop_constraint(
                "uq_supply_business_product_variant", type_="unique"
            )

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "supply", "product_variant") and not _column_exists(
        inspector, "supply", "product_surtido"
    ):
        with op.batch_alter_table("supply", schema=None) as batch_op:
            batch_op.alter_column("product_variant", new_column_name="product_surtido")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "supply", "product_surtido") and not _unique_exists(
        inspector, "supply", "uq_supply_business_product_surtido"
    ):
        with op.batch_alter_table("supply", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_supply_business_product_surtido",
                ["business_id", "product_surtido"],
            )
