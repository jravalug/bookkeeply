"""add supply and inventory movement models

Revision ID: a91c3e7f4d2b
Revises: ffcfa3287a86
Create Date: 2026-03-09 18:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "a91c3e7f4d2b"
down_revision = "ffcfa3287a86"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "supply" not in existing_tables:
        op.create_table(
            "supply",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("inventory_item_id", sa.Integer(), nullable=False),
            sa.Column("product_surtido", sa.String(length=120), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
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
                "product_surtido",
                name="uq_supply_business_product_surtido",
            ),
        )

    inspector = sa.inspect(bind)
    supply_indexes = {index["name"] for index in inspector.get_indexes("supply")}
    if "ix_supply_business_id" not in supply_indexes:
        op.create_index(
            "ix_supply_business_id", "supply", ["business_id"], unique=False
        )
    if "ix_supply_inventory_item_id" not in supply_indexes:
        op.create_index(
            "ix_supply_inventory_item_id",
            "supply",
            ["inventory_item_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "inventory_movement" not in existing_tables:
        op.create_table(
            "inventory_movement",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("inventory_item_id", sa.Integer(), nullable=False),
            sa.Column("inventory_id", sa.Integer(), nullable=True),
            sa.Column("movement_type", sa.String(length=30), nullable=False),
            sa.Column("destination", sa.String(length=30), nullable=True),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(length=20), nullable=False),
            sa.Column("unit_cost", sa.Float(), nullable=True),
            sa.Column("total_cost", sa.Float(), nullable=True),
            sa.Column("idempotency_key", sa.String(length=120), nullable=True),
            sa.Column("reference_type", sa.String(length=40), nullable=True),
            sa.Column("reference_id", sa.Integer(), nullable=True),
            sa.Column("document", sa.String(length=80), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "movement_date",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
            sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_item.id"]),
            sa.ForeignKeyConstraint(["inventory_id"], ["inventory.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        )

    inspector = sa.inspect(bind)
    movement_indexes = {
        index["name"] for index in inspector.get_indexes("inventory_movement")
    }

    if "ix_inventory_movement_business_id" not in movement_indexes:
        op.create_index(
            "ix_inventory_movement_business_id",
            "inventory_movement",
            ["business_id"],
            unique=False,
        )
    if "ix_inventory_movement_inventory_item_id" not in movement_indexes:
        op.create_index(
            "ix_inventory_movement_inventory_item_id",
            "inventory_movement",
            ["inventory_item_id"],
            unique=False,
        )
    if "ix_inventory_movement_inventory_id" not in movement_indexes:
        op.create_index(
            "ix_inventory_movement_inventory_id",
            "inventory_movement",
            ["inventory_id"],
            unique=False,
        )
    if "ix_inventory_movement_movement_type" not in movement_indexes:
        op.create_index(
            "ix_inventory_movement_movement_type",
            "inventory_movement",
            ["movement_type"],
            unique=False,
        )
    if "ix_inventory_movement_destination" not in movement_indexes:
        op.create_index(
            "ix_inventory_movement_destination",
            "inventory_movement",
            ["destination"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "inventory_movement" in existing_tables:
        movement_indexes = {
            index["name"] for index in inspector.get_indexes("inventory_movement")
        }
        if "ix_inventory_movement_destination" in movement_indexes:
            op.drop_index(
                "ix_inventory_movement_destination", table_name="inventory_movement"
            )
        if "ix_inventory_movement_movement_type" in movement_indexes:
            op.drop_index(
                "ix_inventory_movement_movement_type", table_name="inventory_movement"
            )
        if "ix_inventory_movement_inventory_id" in movement_indexes:
            op.drop_index(
                "ix_inventory_movement_inventory_id", table_name="inventory_movement"
            )
        if "ix_inventory_movement_inventory_item_id" in movement_indexes:
            op.drop_index(
                "ix_inventory_movement_inventory_item_id",
                table_name="inventory_movement",
            )
        if "ix_inventory_movement_business_id" in movement_indexes:
            op.drop_index(
                "ix_inventory_movement_business_id", table_name="inventory_movement"
            )

        op.drop_table("inventory_movement")

    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "supply" in existing_tables:
        supply_indexes = {index["name"] for index in inspector.get_indexes("supply")}
        if "ix_supply_inventory_item_id" in supply_indexes:
            op.drop_index("ix_supply_inventory_item_id", table_name="supply")
        if "ix_supply_business_id" in supply_indexes:
            op.drop_index("ix_supply_business_id", table_name="supply")

        op.drop_table("supply")
