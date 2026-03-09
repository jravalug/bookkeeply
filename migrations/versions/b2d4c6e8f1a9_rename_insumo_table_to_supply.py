"""rename insumo table to supply for compatibility

Revision ID: b2d4c6e8f1a9
Revises: a91c3e7f4d2b
Create Date: 2026-03-09 20:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b2d4c6e8f1a9"
down_revision = "a91c3e7f4d2b"
branch_labels = None
depends_on = None


_INDEX_RENAMES = {
    "ix_insumo_business_id": "ix_supply_business_id",
    "ix_insumo_inventory_item_id": "ix_supply_inventory_item_id",
}


def _refresh_inspector(bind):
    return sa.inspect(bind)


def upgrade():
    bind = op.get_bind()
    inspector = _refresh_inspector(bind)
    tables = inspector.get_table_names()

    if "insumo" in tables and "supply" not in tables:
        op.rename_table("insumo", "supply")

    inspector = _refresh_inspector(bind)
    tables = inspector.get_table_names()
    if "supply" not in tables:
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes("supply")}

    for old_name, new_name in _INDEX_RENAMES.items():
        if old_name in existing_indexes:
            op.drop_index(old_name, table_name="supply")
            existing_indexes.remove(old_name)

        if new_name not in existing_indexes:
            column = (
                "business_id"
                if new_name.endswith("business_id")
                else "inventory_item_id"
            )
            op.create_index(new_name, "supply", [column], unique=False)
            existing_indexes.add(new_name)


def downgrade():
    bind = op.get_bind()
    inspector = _refresh_inspector(bind)
    tables = inspector.get_table_names()

    if "supply" not in tables:
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes("supply")}

    for old_name, new_name in _INDEX_RENAMES.items():
        if new_name in existing_indexes:
            op.drop_index(new_name, table_name="supply")
            existing_indexes.remove(new_name)

        if old_name not in existing_indexes:
            column = (
                "business_id"
                if old_name.endswith("business_id")
                else "inventory_item_id"
            )
            op.create_index(old_name, "supply", [column], unique=False)
            existing_indexes.add(old_name)

    inspector = _refresh_inspector(bind)
    tables = inspector.get_table_names()
    if "supply" in tables and "insumo" not in tables:
        op.rename_table("supply", "insumo")
