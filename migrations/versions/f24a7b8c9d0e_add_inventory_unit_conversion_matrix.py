"""add inventory unit conversion matrix

Revision ID: f24a7b8c9d0e
Revises: f23f6a7b8c9d
Create Date: 2026-03-09 22:28:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f24a7b8c9d0e"
down_revision = "f23f6a7b8c9d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_unit_conversion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("from_unit", sa.String(length=20), nullable=False),
        sa.Column("to_unit", sa.String(length=20), nullable=False),
        sa.Column("factor", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            "from_unit",
            "to_unit",
            name="uq_inventory_unit_conversion_business_item_units",
        ),
        sa.CheckConstraint("factor > 0", name="ck_inventory_unit_conversion_factor"),
    )
    op.create_index(
        "ix_inventory_unit_conversion_business_id",
        "inventory_unit_conversion",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_unit_conversion_inventory_item_id",
        "inventory_unit_conversion",
        ["inventory_item_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_inventory_unit_conversion_inventory_item_id",
        table_name="inventory_unit_conversion",
    )
    op.drop_index(
        "ix_inventory_unit_conversion_business_id",
        table_name="inventory_unit_conversion",
    )
    op.drop_table("inventory_unit_conversion")
