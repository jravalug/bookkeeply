"""add lot_code to inventory_movement

Revision ID: f7b1c2d3e4f5
Revises: f6a7b8c9d0e1
Create Date: 2026-03-09 18:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f7b1c2d3e4f5"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _index_exists(inspector, table_name, index_name):
    return any(
        index["name"] == index_name for index in inspector.get_indexes(table_name)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inventory_movement" not in inspector.get_table_names():
        return

    if not _column_exists(inspector, "inventory_movement", "lot_code"):
        with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("lot_code", sa.String(length=80), nullable=True)
            )

    inspector = sa.inspect(bind)
    if not _index_exists(
        inspector, "inventory_movement", "ix_inventory_movement_lot_code"
    ):
        op.create_index(
            "ix_inventory_movement_lot_code",
            "inventory_movement",
            ["lot_code"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inventory_movement" not in inspector.get_table_names():
        return

    if _index_exists(inspector, "inventory_movement", "ix_inventory_movement_lot_code"):
        op.drop_index("ix_inventory_movement_lot_code", table_name="inventory_movement")

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "inventory_movement", "lot_code"):
        with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
            batch_op.drop_column("lot_code")
