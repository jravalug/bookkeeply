"""add business account adoption table

Revision ID: d7f2a9c4e1b8
Revises: c4e8f1a9b7d2
Create Date: 2026-03-09 21:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d7f2a9c4e1b8"
down_revision = "c4e8f1a9b7d2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "business_account_adoption" not in existing_tables:
        op.create_table(
            "business_account_adoption",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("business_id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "adopted_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("removed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["business_id"], ["business.id"]),
            sa.ForeignKeyConstraint(["account_id"], ["ac_account.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "business_id",
                "account_id",
                name="uq_business_account_adoption_business_account",
            ),
        )

    inspector = sa.inspect(bind)
    indexes = {
        index["name"] for index in inspector.get_indexes("business_account_adoption")
    }

    if "ix_business_account_adoption_business_id" not in indexes:
        op.create_index(
            "ix_business_account_adoption_business_id",
            "business_account_adoption",
            ["business_id"],
            unique=False,
        )
    if "ix_business_account_adoption_account_id" not in indexes:
        op.create_index(
            "ix_business_account_adoption_account_id",
            "business_account_adoption",
            ["account_id"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "business_account_adoption" not in existing_tables:
        return

    indexes = {
        index["name"] for index in inspector.get_indexes("business_account_adoption")
    }

    if "ix_business_account_adoption_account_id" in indexes:
        op.drop_index(
            "ix_business_account_adoption_account_id",
            table_name="business_account_adoption",
        )
    if "ix_business_account_adoption_business_id" in indexes:
        op.drop_index(
            "ix_business_account_adoption_business_id",
            table_name="business_account_adoption",
        )

    op.drop_table("business_account_adoption")
