"""add inventory sales floor stock table

Revision ID: f8a1b2c3d4e5
Revises: f7b1c2d3e4f5
Create Date: 2026-03-09 19:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f8a1b2c3d4e5"
down_revision = "f7b1c2d3e4f5"
branch_labels = None
depends_on = None


def _index_exists(inspector, table_name, index_name):
    return any(
        index["name"] == index_name for index in inspector.get_indexes(table_name)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inventory_sales_floor_stock" not in inspector.get_table_names():
        op.create_table(
            "inventory_sales_floor_stock",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("inventory_item_id", sa.Integer(), nullable=False),
            sa.Column(
                "current_quantity", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column("min_quantity", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_quantity", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
            sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_item.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "business_id",
                "inventory_item_id",
                name="uq_sales_floor_stock_business_item",
            ),
        )

    inspector = sa.inspect(bind)
    if not _index_exists(
        inspector,
        "inventory_sales_floor_stock",
        "ix_inventory_sales_floor_stock_business_id",
    ):
        op.create_index(
            "ix_inventory_sales_floor_stock_business_id",
            "inventory_sales_floor_stock",
            ["business_id"],
            unique=False,
        )

    if not _index_exists(
        inspector,
        "inventory_sales_floor_stock",
        "ix_inventory_sales_floor_stock_inventory_item_id",
    ):
        op.create_index(
            "ix_inventory_sales_floor_stock_inventory_item_id",
            "inventory_sales_floor_stock",
            ["inventory_item_id"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inventory_sales_floor_stock" not in inspector.get_table_names():
        return

    if _index_exists(
        inspector,
        "inventory_sales_floor_stock",
        "ix_inventory_sales_floor_stock_inventory_item_id",
    ):
        op.drop_index(
            "ix_inventory_sales_floor_stock_inventory_item_id",
            table_name="inventory_sales_floor_stock",
        )

    if _index_exists(
        inspector,
        "inventory_sales_floor_stock",
        "ix_inventory_sales_floor_stock_business_id",
    ):
        op.drop_index(
            "ix_inventory_sales_floor_stock_business_id",
            table_name="inventory_sales_floor_stock",
        )

    op.drop_table("inventory_sales_floor_stock")
