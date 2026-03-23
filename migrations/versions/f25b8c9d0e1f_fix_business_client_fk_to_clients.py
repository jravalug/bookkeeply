"""fix business client fk to clients

Revision ID: f25b8c9d0e1f
Revises: f24a7b8c9d0e
Create Date: 2026-03-22 18:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f25b8c9d0e1f"
down_revision = "f24a7b8c9d0e"
branch_labels = None
depends_on = None


def _get_client_fk(inspector):
    foreign_keys = inspector.get_foreign_keys("business")
    for foreign_key in foreign_keys:
        if foreign_key.get("constrained_columns") == ["client_id"]:
            return foreign_key
    return None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())
    if "business" not in table_names or "clients" not in table_names:
        return

    client_fk = _get_client_fk(inspector)
    if not client_fk:
        return

    referred_table = client_fk.get("referred_table")
    if referred_table == "clients":
        return

    fk_name = client_fk.get("name") or "fk_business_client_id"
    placeholder_created = False

    if referred_table == "clients_old_taxdrop" and referred_table not in table_names:
        op.execute(sa.text("CREATE TABLE clients_old_taxdrop (id INTEGER PRIMARY KEY)"))
        placeholder_created = True

    try:
        with op.batch_alter_table("business", schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_business_client_id",
                "clients",
                ["client_id"],
                ["id"],
            )
    finally:
        if placeholder_created:
            op.execute(sa.text("DROP TABLE IF EXISTS clients_old_taxdrop"))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())
    if "business" not in table_names or "clients_old_taxdrop" not in table_names:
        return

    client_fk = _get_client_fk(inspector)
    if not client_fk:
        return

    referred_table = client_fk.get("referred_table")
    if referred_table == "clients_old_taxdrop":
        return

    fk_name = client_fk.get("name") or "fk_business_client_id"

    with op.batch_alter_table("business", schema=None) as batch_op:
        batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_business_client_id",
            "clients_old_taxdrop",
            ["client_id"],
            ["id"],
        )
