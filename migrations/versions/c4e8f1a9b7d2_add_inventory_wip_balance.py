"""add inventory_wip_balance table

Revision ID: c4e8f1a9b7d2
Revises: b2d4c6e8f1a9
Create Date: 2026-03-09 21:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c4e8f1a9b7d2"
down_revision = "b2d4c6e8f1a9"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "inventory_wip_balance" not in existing_tables:
        op.create_table(
            "inventory_wip_balance",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("inventory_item_id", sa.Integer(), nullable=False),
            sa.Column("source_inventory_id", sa.Integer(), nullable=True),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("remaining_quantity", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
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
            sa.ForeignKeyConstraint(["source_inventory_id"], ["inventory.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "status IN ('open', 'finished', 'waste')",
                name="ck_inventory_wip_balance_status",
            ),
        )

    inspector = sa.inspect(bind)
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("inventory_wip_balance")
    }

    if "ix_inventory_wip_balance_business_id" not in existing_indexes:
        op.create_index(
            "ix_inventory_wip_balance_business_id",
            "inventory_wip_balance",
            ["business_id"],
            unique=False,
        )
    if "ix_inventory_wip_balance_inventory_item_id" not in existing_indexes:
        op.create_index(
            "ix_inventory_wip_balance_inventory_item_id",
            "inventory_wip_balance",
            ["inventory_item_id"],
            unique=False,
        )
    if "ix_inventory_wip_balance_source_inventory_id" not in existing_indexes:
        op.create_index(
            "ix_inventory_wip_balance_source_inventory_id",
            "inventory_wip_balance",
            ["source_inventory_id"],
            unique=False,
        )
    if "ix_inventory_wip_balance_status" not in existing_indexes:
        op.create_index(
            "ix_inventory_wip_balance_status",
            "inventory_wip_balance",
            ["status"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "inventory_wip_balance" not in existing_tables:
        return

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("inventory_wip_balance")
    }

    if "ix_inventory_wip_balance_status" in existing_indexes:
        op.drop_index(
            "ix_inventory_wip_balance_status",
            table_name="inventory_wip_balance",
        )
    if "ix_inventory_wip_balance_source_inventory_id" in existing_indexes:
        op.drop_index(
            "ix_inventory_wip_balance_source_inventory_id",
            table_name="inventory_wip_balance",
        )
    if "ix_inventory_wip_balance_inventory_item_id" in existing_indexes:
        op.drop_index(
            "ix_inventory_wip_balance_inventory_item_id",
            table_name="inventory_wip_balance",
        )
    if "ix_inventory_wip_balance_business_id" in existing_indexes:
        op.drop_index(
            "ix_inventory_wip_balance_business_id",
            table_name="inventory_wip_balance",
        )

    op.drop_table("inventory_wip_balance")
