"""add inventory ledger and mixed sale breakdown

Revision ID: fb3c4d5e6f7a
Revises: fa2b3c4d5e6f
Create Date: 2026-03-09 22:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "fb3c4d5e6f7a"
down_revision = "fa2b3c4d5e6f"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "inventory_ledger_entry"):
        op.create_table(
            "inventory_ledger_entry",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("movement_id", sa.Integer(), nullable=False),
            sa.Column("movement_type", sa.String(length=30), nullable=False),
            sa.Column("destination", sa.String(length=30), nullable=True),
            sa.Column("source_bucket", sa.String(length=30), nullable=False),
            sa.Column("destination_bucket", sa.String(length=30), nullable=False),
            sa.Column("source_account_code", sa.String(length=20), nullable=True),
            sa.Column("destination_account_code", sa.String(length=20), nullable=True),
            sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
            sa.Column("unit", sa.String(length=20), nullable=False),
            sa.Column("unit_cost", sa.Float(), nullable=True),
            sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "valuation_method",
                sa.String(length=20),
                nullable=False,
                server_default="fifo",
            ),
            sa.Column("document", sa.String(length=80), nullable=True),
            sa.Column("reference_type", sa.String(length=40), nullable=True),
            sa.Column("reference_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.CheckConstraint("amount >= 0", name="ck_inventory_ledger_entry_amount"),
            sa.CheckConstraint(
                "valuation_method IN ('fifo', 'fefo', 'manual')",
                name="ck_inventory_ledger_entry_valuation_method",
            ),
            sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
            sa.ForeignKeyConstraint(["movement_id"], ["inventory_movement.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("movement_id"),
        )
        op.create_index(
            "ix_inventory_ledger_entry_business_id",
            "inventory_ledger_entry",
            ["business_id"],
            unique=False,
        )
        op.create_index(
            "ix_inventory_ledger_entry_movement_id",
            "inventory_ledger_entry",
            ["movement_id"],
            unique=True,
        )
        op.create_index(
            "ix_inventory_ledger_entry_movement_type",
            "inventory_ledger_entry",
            ["movement_type"],
            unique=False,
        )
        op.create_index(
            "ix_inventory_ledger_entry_destination",
            "inventory_ledger_entry",
            ["destination"],
            unique=False,
        )
        op.create_index(
            "ix_inventory_ledger_entry_source_account_code",
            "inventory_ledger_entry",
            ["source_account_code"],
            unique=False,
        )
        op.create_index(
            "ix_inventory_ledger_entry_destination_account_code",
            "inventory_ledger_entry",
            ["destination_account_code"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "inventory_sale_cost_breakdown"):
        op.create_table(
            "inventory_sale_cost_breakdown",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("sale_id", sa.Integer(), nullable=False),
            sa.Column(
                "production_account_code",
                sa.String(length=20),
                nullable=False,
                server_default="1586",
            ),
            sa.Column(
                "merchandise_account_code",
                sa.String(length=20),
                nullable=False,
                server_default="1587",
            ),
            sa.Column(
                "production_cost", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column(
                "merchandise_cost", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.CheckConstraint(
                "production_cost >= 0",
                name="ck_inventory_sale_cost_breakdown_production_cost",
            ),
            sa.CheckConstraint(
                "merchandise_cost >= 0",
                name="ck_inventory_sale_cost_breakdown_merchandise_cost",
            ),
            sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
            sa.ForeignKeyConstraint(["sale_id"], ["sale.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("sale_id"),
        )
        op.create_index(
            "ix_inventory_sale_cost_breakdown_business_id",
            "inventory_sale_cost_breakdown",
            ["business_id"],
            unique=False,
        )
        op.create_index(
            "ix_inventory_sale_cost_breakdown_sale_id",
            "inventory_sale_cost_breakdown",
            ["sale_id"],
            unique=True,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "inventory_sale_cost_breakdown"):
        op.drop_index(
            "ix_inventory_sale_cost_breakdown_sale_id",
            table_name="inventory_sale_cost_breakdown",
        )
        op.drop_index(
            "ix_inventory_sale_cost_breakdown_business_id",
            table_name="inventory_sale_cost_breakdown",
        )
        op.drop_table("inventory_sale_cost_breakdown")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "inventory_ledger_entry"):
        op.drop_index(
            "ix_inventory_ledger_entry_destination_account_code",
            table_name="inventory_ledger_entry",
        )
        op.drop_index(
            "ix_inventory_ledger_entry_source_account_code",
            table_name="inventory_ledger_entry",
        )
        op.drop_index(
            "ix_inventory_ledger_entry_destination",
            table_name="inventory_ledger_entry",
        )
        op.drop_index(
            "ix_inventory_ledger_entry_movement_type",
            table_name="inventory_ledger_entry",
        )
        op.drop_index(
            "ix_inventory_ledger_entry_movement_id",
            table_name="inventory_ledger_entry",
        )
        op.drop_index(
            "ix_inventory_ledger_entry_business_id",
            table_name="inventory_ledger_entry",
        )
        op.drop_table("inventory_ledger_entry")
