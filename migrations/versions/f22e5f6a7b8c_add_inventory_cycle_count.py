"""add inventory cycle count

Revision ID: f22e5f6a7b8c
Revises: f21d4e5f6a7b
Create Date: 2026-03-09 21:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f22e5f6a7b8c"
down_revision = "f21d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_cycle_count",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column(
            "location", sa.String(length=30), nullable=False, server_default="warehouse"
        ),
        sa.Column(
            "theoretical_quantity", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("counted_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "difference_quantity", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("proposed_adjustment_kind", sa.String(length=20), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="pending"
        ),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column(
            "counted_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("observation", sa.Text(), nullable=True),
        sa.Column("applied_movement_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["applied_movement_id"], ["inventory_movement.id"]),
        sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "location IN ('warehouse')", name="ck_inventory_cycle_count_location"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'applied')", name="ck_inventory_cycle_count_status"
        ),
        sa.CheckConstraint(
            "proposed_adjustment_kind IS NULL OR proposed_adjustment_kind IN ('positive', 'negative')",
            name="ck_inventory_cycle_count_proposed_adjustment_kind",
        ),
    )
    op.create_index(
        "ix_inventory_cycle_count_business_id",
        "inventory_cycle_count",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_cycle_count_inventory_item_id",
        "inventory_cycle_count",
        ["inventory_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_cycle_count_applied_movement_id",
        "inventory_cycle_count",
        ["applied_movement_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_inventory_cycle_count_applied_movement_id",
        table_name="inventory_cycle_count",
    )
    op.drop_index(
        "ix_inventory_cycle_count_inventory_item_id", table_name="inventory_cycle_count"
    )
    op.drop_index(
        "ix_inventory_cycle_count_business_id", table_name="inventory_cycle_count"
    )
    op.drop_table("inventory_cycle_count")
