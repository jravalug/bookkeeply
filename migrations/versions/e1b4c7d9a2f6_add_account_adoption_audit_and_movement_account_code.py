"""add account adoption audit and movement account code

Revision ID: e1b4c7d9a2f6
Revises: d7f2a9c4e1b8
Create Date: 2026-03-09 22:25:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e1b4c7d9a2f6"
down_revision = "d7f2a9c4e1b8"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "business_account_adoption_audit" not in existing_tables:
        op.create_table(
            "business_account_adoption_audit",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=30), nullable=False),
            sa.Column("actor", sa.String(length=120), nullable=True),
            sa.Column("source", sa.String(length=50), nullable=True),
            sa.Column("previous_is_active", sa.Boolean(), nullable=True),
            sa.Column("new_is_active", sa.Boolean(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
            sa.ForeignKeyConstraint(["account_id"], ["ac_account.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if "business_account_adoption_audit" in inspector.get_table_names():
        indexes = {
            index["name"]
            for index in inspector.get_indexes("business_account_adoption_audit")
        }
        if "ix_business_account_adoption_audit_business_id" not in indexes:
            op.create_index(
                "ix_business_account_adoption_audit_business_id",
                "business_account_adoption_audit",
                ["business_id"],
                unique=False,
            )
        if "ix_business_account_adoption_audit_account_id" not in indexes:
            op.create_index(
                "ix_business_account_adoption_audit_account_id",
                "business_account_adoption_audit",
                ["account_id"],
                unique=False,
            )
        if "ix_business_account_adoption_audit_action" not in indexes:
            op.create_index(
                "ix_business_account_adoption_audit_action",
                "business_account_adoption_audit",
                ["action"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if "inventory_movement" in inspector.get_table_names() and not _column_exists(
        inspector, "inventory_movement", "account_code"
    ):
        with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("account_code", sa.String(length=20), nullable=True)
            )

    inspector = sa.inspect(bind)
    if "inventory_movement" in inspector.get_table_names():
        movement_indexes = {
            index["name"] for index in inspector.get_indexes("inventory_movement")
        }
        if "ix_inventory_movement_account_code" not in movement_indexes:
            op.create_index(
                "ix_inventory_movement_account_code",
                "inventory_movement",
                ["account_code"],
                unique=False,
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "inventory_movement" in inspector.get_table_names():
        movement_indexes = {
            index["name"] for index in inspector.get_indexes("inventory_movement")
        }
        if "ix_inventory_movement_account_code" in movement_indexes:
            op.drop_index(
                "ix_inventory_movement_account_code",
                table_name="inventory_movement",
            )

        if _column_exists(inspector, "inventory_movement", "account_code"):
            with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
                batch_op.drop_column("account_code")

    inspector = sa.inspect(bind)
    if "business_account_adoption_audit" in inspector.get_table_names():
        indexes = {
            index["name"]
            for index in inspector.get_indexes("business_account_adoption_audit")
        }
        if "ix_business_account_adoption_audit_action" in indexes:
            op.drop_index(
                "ix_business_account_adoption_audit_action",
                table_name="business_account_adoption_audit",
            )
        if "ix_business_account_adoption_audit_account_id" in indexes:
            op.drop_index(
                "ix_business_account_adoption_audit_account_id",
                table_name="business_account_adoption_audit",
            )
        if "ix_business_account_adoption_audit_business_id" in indexes:
            op.drop_index(
                "ix_business_account_adoption_audit_business_id",
                table_name="business_account_adoption_audit",
            )

        op.drop_table("business_account_adoption_audit")
