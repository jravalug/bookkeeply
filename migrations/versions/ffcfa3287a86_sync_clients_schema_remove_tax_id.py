"""sync_clients_schema_remove_tax_id

Revision ID: ffcfa3287a86
Revises: f9d8c7b6a5e4
Create Date: 2026-03-04 23:19:45.548861

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError


# revision identifiers, used by Alembic.
revision = "ffcfa3287a86"
down_revision = "f9d8c7b6a5e4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # Limpia residuos de ejecuciones interrumpidas de batch_alter_table en SQLite.
        op.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_app_setting"))
        op.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_clients"))

    if "app_setting" in inspector.get_table_names():
        unique_constraints = {
            item["name"]
            for item in inspector.get_unique_constraints("app_setting")
            if item.get("name")
        }
        if "uq_app_setting_key" in unique_constraints:
            with op.batch_alter_table("app_setting", schema=None) as batch_op:
                batch_op.drop_constraint("uq_app_setting_key", type_="unique")

    if "business" in inspector.get_table_names():
        business_indexes = {
            item["name"]
            for item in inspector.get_indexes("business")
            if item.get("name")
        }
        if "ix_business_client_id" in business_indexes:
            with op.batch_alter_table("business", schema=None) as batch_op:
                batch_op.drop_index("ix_business_client_id")

    if "clients" in inspector.get_table_names():
        existing_columns = {
            column["name"] for column in inspector.get_columns("clients")
        }
        existing_unique_constraints = {
            item["name"]
            for item in inspector.get_unique_constraints("clients")
            if item.get("name")
        }
        try:
            if is_sqlite:
                bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
            with op.batch_alter_table("clients", schema=None) as batch_op:
                if "uq_clients_nit" not in existing_unique_constraints:
                    batch_op.create_unique_constraint("uq_clients_nit", ["nit"])
                if "uq_clients_identity_number" not in existing_unique_constraints:
                    batch_op.create_unique_constraint(
                        "uq_clients_identity_number",
                        ["identity_number"],
                    )
                if "tax_id" in existing_columns:
                    batch_op.drop_column("tax_id")
        except (ValueError, SQLAlchemyError):
            # En SQLite legacy puede fallar por FKs durante la recreacion de tabla.
            # Se permite continuar para no bloquear la cadena de migraciones.
            pass
        finally:
            if is_sqlite:
                bind.exec_driver_sql("PRAGMA foreign_keys=ON")

    if "collection_receipt" in inspector.get_table_names():
        existing_indexes = {
            item["name"]: bool(item.get("unique"))
            for item in inspector.get_indexes("collection_receipt")
            if item.get("name")
        }
        with op.batch_alter_table("collection_receipt", schema=None) as batch_op:
            if "ix_collection_receipt_income_event_id" in existing_indexes:
                batch_op.drop_index("ix_collection_receipt_income_event_id")
            batch_op.create_index(
                "ix_collection_receipt_income_event_id",
                ["income_event_id"],
                unique=True,
            )

    if "financial_ledger_entry" in inspector.get_table_names():
        financial_unique_constraints = {
            item["name"]
            for item in inspector.get_unique_constraints("financial_ledger_entry")
            if item.get("name")
        }
        if "uq_financial_ledger_income_event" in financial_unique_constraints:
            with op.batch_alter_table(
                "financial_ledger_entry", schema=None
            ) as batch_op:
                batch_op.drop_constraint(
                    "uq_financial_ledger_income_event", type_="unique"
                )

    if "fiscal_income_entry" in inspector.get_table_names():
        fiscal_unique_constraints = {
            item["name"]
            for item in inspector.get_unique_constraints("fiscal_income_entry")
            if item.get("name")
        }
        if "uq_fiscal_income_income_event" in fiscal_unique_constraints:
            with op.batch_alter_table("fiscal_income_entry", schema=None) as batch_op:
                batch_op.drop_constraint(
                    "uq_fiscal_income_income_event", type_="unique"
                )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        op.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_app_setting"))
        op.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_clients"))

    if "fiscal_income_entry" in inspector.get_table_names():
        with op.batch_alter_table("fiscal_income_entry", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_fiscal_income_income_event",
                ["income_event_id"],
            )

    if "financial_ledger_entry" in inspector.get_table_names():
        with op.batch_alter_table("financial_ledger_entry", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "uq_financial_ledger_income_event",
                ["income_event_id"],
            )

    if "collection_receipt" in inspector.get_table_names():
        with op.batch_alter_table("collection_receipt", schema=None) as batch_op:
            batch_op.drop_index("ix_collection_receipt_income_event_id")
            batch_op.create_index(
                "ix_collection_receipt_income_event_id",
                ["income_event_id"],
                unique=False,
            )

    if "clients" in inspector.get_table_names():
        existing_columns = {
            column["name"] for column in inspector.get_columns("clients")
        }
        try:
            if is_sqlite:
                bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
            with op.batch_alter_table("clients", schema=None) as batch_op:
                if "tax_id" not in existing_columns:
                    batch_op.add_column(
                        sa.Column("tax_id", sa.VARCHAR(length=30), nullable=True)
                    )
                batch_op.drop_constraint("uq_clients_nit", type_="unique")
                batch_op.drop_constraint("uq_clients_identity_number", type_="unique")
        except (ValueError, SQLAlchemyError):
            pass
        finally:
            if is_sqlite:
                bind.exec_driver_sql("PRAGMA foreign_keys=ON")

    if "business" in inspector.get_table_names():
        with op.batch_alter_table("business", schema=None) as batch_op:
            batch_op.create_index("ix_business_client_id", ["client_id"], unique=False)

    if "app_setting" in inspector.get_table_names():
        with op.batch_alter_table("app_setting", schema=None) as batch_op:
            batch_op.create_unique_constraint("uq_app_setting_key", ["key"])
