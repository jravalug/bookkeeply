"""add inventory generic/specific catalog and link supply

Revision ID: f5d2a1b3c4e6
Revises: f4c8e1b2d3a9
Create Date: 2026-03-09 16:55:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f5d2a1b3c4e6"
down_revision = "f4c8e1b2d3a9"
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


def _unique_exists(inspector, table_name, constraint_name):
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _rename_supply_variant_column_if_needed(bind):
    inspector = sa.inspect(bind)
    if "supply" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("supply")}
    if "product_variant" in columns or "product_surtido" not in columns:
        return

    with op.batch_alter_table("supply", schema=None) as batch_op:
        batch_op.alter_column("product_surtido", new_column_name="product_variant")


def _replace_legacy_unique_constraint_if_needed(bind):
    inspector = sa.inspect(bind)
    if "supply" not in inspector.get_table_names():
        return

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("supply")
        if constraint.get("name")
    }

    if "uq_supply_business_product_surtido" in unique_constraints:
        with op.batch_alter_table("supply", schema=None) as batch_op:
            batch_op.drop_constraint(
                "uq_supply_business_product_surtido", type_="unique"
            )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = inspector.get_table_names()

    _rename_supply_variant_column_if_needed(bind)
    _replace_legacy_unique_constraint_if_needed(bind)

    if "inventory_product_generic" not in tables:
        op.create_table(
            "inventory_product_generic",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
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
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_inventory_product_generic_name"),
        )

    inspector = sa.inspect(bind)
    if "inventory_product_specific" not in inspector.get_table_names():
        op.create_table(
            "inventory_product_specific",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("generic_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
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
            sa.ForeignKeyConstraint(["generic_id"], ["inventory_product_generic.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "generic_id",
                "name",
                name="uq_inventory_product_specific_generic_name",
            ),
        )

    inspector = sa.inspect(bind)
    if (
        "inventory_product_specific" in inspector.get_table_names()
        and not _index_exists(
            inspector,
            "inventory_product_specific",
            "ix_inventory_product_specific_generic_id",
        )
    ):
        op.create_index(
            "ix_inventory_product_specific_generic_id",
            "inventory_product_specific",
            ["generic_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if "supply" in inspector.get_table_names() and not _column_exists(
        inspector, "supply", "product_specific_id"
    ):
        with op.batch_alter_table("supply", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("product_specific_id", sa.Integer(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_supply_product_specific_id",
                "inventory_product_specific",
                ["product_specific_id"],
                ["id"],
            )

    inspector = sa.inspect(bind)
    if "supply" in inspector.get_table_names() and not _index_exists(
        inspector, "supply", "ix_supply_product_specific_id"
    ):
        op.create_index(
            "ix_supply_product_specific_id",
            "supply",
            ["product_specific_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if "supply" in inspector.get_table_names() and not _unique_exists(
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

    if "supply" in inspector.get_table_names():
        if _index_exists(inspector, "supply", "ix_supply_product_specific_id"):
            op.drop_index("ix_supply_product_specific_id", table_name="supply")

        if _column_exists(inspector, "supply", "product_specific_id"):
            with op.batch_alter_table("supply", schema=None) as batch_op:
                batch_op.drop_constraint(
                    "fk_supply_product_specific_id", type_="foreignkey"
                )
                batch_op.drop_column("product_specific_id")

    inspector = sa.inspect(bind)
    if "inventory_product_specific" in inspector.get_table_names():
        if _index_exists(
            inspector,
            "inventory_product_specific",
            "ix_inventory_product_specific_generic_id",
        ):
            op.drop_index(
                "ix_inventory_product_specific_generic_id",
                table_name="inventory_product_specific",
            )
        op.drop_table("inventory_product_specific")

    inspector = sa.inspect(bind)
    if "inventory_product_generic" in inspector.get_table_names():
        op.drop_table("inventory_product_generic")
