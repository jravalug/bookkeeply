"""add business subaccounts and audit

Revision ID: fa2b3c4d5e6f
Revises: f9c1d2e3a4b5
Create Date: 2026-03-09 21:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "fa2b3c4d5e6f"
down_revision = "f9c1d2e3a4b5"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def _unique_exists(inspector, table_name, unique_name):
    return any(
        constraint.get("name") == unique_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _foreign_key_exists(inspector, table_name, fk_name):
    return any(
        fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "business_account_adoption") and not _unique_exists(
        inspector,
        "business_account_adoption",
        "uq_business_account_adoption_business_id_id",
    ):
        with op.batch_alter_table("business_account_adoption", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_business_account_adoption_business_id_id",
                ["business_id", "id"],
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "business_sub_account"):
        op.create_table(
            "business_sub_account",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("business_account_adoption_id", sa.Integer(), nullable=False),
            sa.Column("template_subaccount_id", sa.Integer(), nullable=True),
            sa.Column("code", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
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
            sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
            sa.ForeignKeyConstraint(
                ["business_account_adoption_id"],
                ["business_account_adoption.id"],
            ),
            sa.ForeignKeyConstraint(["template_subaccount_id"], ["ac_sub_account.id"]),
            sa.ForeignKeyConstraint(
                ["business_id", "business_account_adoption_id"],
                [
                    "business_account_adoption.business_id",
                    "business_account_adoption.id",
                ],
                name="fk_business_sub_account_adoption_same_business",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "business_id",
                "code",
                name="uq_business_sub_account_business_code",
            ),
        )
        op.create_index(
            "ix_business_sub_account_business_id",
            "business_sub_account",
            ["business_id"],
            unique=False,
        )
        op.create_index(
            "ix_business_sub_account_business_account_adoption_id",
            "business_sub_account",
            ["business_account_adoption_id"],
            unique=False,
        )
        op.create_index(
            "ix_business_sub_account_template_subaccount_id",
            "business_sub_account",
            ["template_subaccount_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "business_sub_account_audit"):
        op.create_table(
            "business_sub_account_audit",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("business_sub_account_id", sa.Integer(), nullable=True),
            sa.Column("business_account_adoption_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=30), nullable=False),
            sa.Column("actor", sa.String(length=120), nullable=True),
            sa.Column("source", sa.String(length=50), nullable=True),
            sa.Column("previous_code", sa.String(length=20), nullable=True),
            sa.Column("new_code", sa.String(length=20), nullable=True),
            sa.Column("previous_name", sa.String(length=100), nullable=True),
            sa.Column("new_name", sa.String(length=100), nullable=True),
            sa.Column("previous_is_active", sa.Boolean(), nullable=True),
            sa.Column("new_is_active", sa.Boolean(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            ),
            sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
            sa.ForeignKeyConstraint(
                ["business_sub_account_id"],
                ["business_sub_account.id"],
            ),
            sa.ForeignKeyConstraint(
                ["business_account_adoption_id"],
                ["business_account_adoption.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_business_sub_account_audit_business_id",
            "business_sub_account_audit",
            ["business_id"],
            unique=False,
        )
        op.create_index(
            "ix_business_sub_account_audit_business_sub_account_id",
            "business_sub_account_audit",
            ["business_sub_account_id"],
            unique=False,
        )
        op.create_index(
            "ix_business_sub_account_audit_business_account_adoption_id",
            "business_sub_account_audit",
            ["business_account_adoption_id"],
            unique=False,
        )
        op.create_index(
            "ix_business_sub_account_audit_action",
            "business_sub_account_audit",
            ["action"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "business_sub_account_audit"):
        op.drop_index(
            "ix_business_sub_account_audit_action",
            table_name="business_sub_account_audit",
        )
        op.drop_index(
            "ix_business_sub_account_audit_business_account_adoption_id",
            table_name="business_sub_account_audit",
        )
        op.drop_index(
            "ix_business_sub_account_audit_business_sub_account_id",
            table_name="business_sub_account_audit",
        )
        op.drop_index(
            "ix_business_sub_account_audit_business_id",
            table_name="business_sub_account_audit",
        )
        op.drop_table("business_sub_account_audit")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "business_sub_account"):
        op.drop_index(
            "ix_business_sub_account_template_subaccount_id",
            table_name="business_sub_account",
        )
        op.drop_index(
            "ix_business_sub_account_business_account_adoption_id",
            table_name="business_sub_account",
        )
        op.drop_index(
            "ix_business_sub_account_business_id",
            table_name="business_sub_account",
        )
        op.drop_table("business_sub_account")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "business_account_adoption") and _unique_exists(
        inspector,
        "business_account_adoption",
        "uq_business_account_adoption_business_id_id",
    ):
        with op.batch_alter_table("business_account_adoption", schema=None) as batch_op:
            batch_op.drop_constraint(
                "uq_business_account_adoption_business_id_id",
                type_="unique",
            )
