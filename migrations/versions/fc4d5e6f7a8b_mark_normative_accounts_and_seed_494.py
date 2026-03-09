"""mark normative accounts and seed initial 494 catalog

Revision ID: fc4d5e6f7a8b
Revises: fb3c4d5e6f7a
Create Date: 2026-03-09 22:35:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "fc4d5e6f7a8b"
down_revision = "fb3c4d5e6f7a"
branch_labels = None
depends_on = None


SEED_ACCOUNTS = [
    ("1586", "Produccion para la venta", True),
    ("1587", "Mercancias para la venta", True),
    ("800", "Gastos de operaciones", True),
]


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def _column_exists(inspector, table_name, column_name):
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "ac_account"):
        return

    if not _column_exists(inspector, "ac_account", "is_normative"):
        with op.batch_alter_table("ac_account", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "is_normative",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                )
            )
            batch_op.create_index(
                "ix_ac_account_is_normative",
                ["is_normative"],
                unique=False,
            )

    account_table = sa.table(
        "ac_account",
        sa.column("id", sa.Integer()),
        sa.column("code", sa.String(length=20)),
        sa.column("name", sa.String(length=100)),
        sa.column("is_normative", sa.Boolean()),
    )

    for code, name, is_normative in SEED_ACCOUNTS:
        existing = bind.execute(
            sa.select(account_table.c.id).where(account_table.c.code == code)
        ).fetchone()
        if existing:
            bind.execute(
                account_table.update()
                .where(account_table.c.id == existing.id)
                .values(is_normative=is_normative)
            )
            continue

        bind.execute(
            account_table.insert().values(
                code=code,
                name=name,
                is_normative=is_normative,
            )
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "ac_account"):
        return

    if _column_exists(inspector, "ac_account", "is_normative"):
        with op.batch_alter_table("ac_account", schema=None) as batch_op:
            batch_op.drop_index("ix_ac_account_is_normative")
            batch_op.drop_column("is_normative")
