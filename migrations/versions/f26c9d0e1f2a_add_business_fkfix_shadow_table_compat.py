"""add business fkfix shadow table compatibility

Revision ID: f26c9d0e1f2a
Revises: f25b8c9d0e1f
Create Date: 2026-03-22 18:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f26c9d0e1f2a"
down_revision = "f25b8c9d0e1f"
branch_labels = None
depends_on = None


def _has_legacy_business_fk_refs(bind):
    rows = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM sqlite_master
            WHERE sql LIKE '%REFERENCES "business_fkfix_old"%'
               OR sql LIKE '%REFERENCES business_fkfix_old%'
            LIMIT 1
            """
        )
    ).fetchall()
    return bool(rows)


def upgrade():
    bind = op.get_bind()

    if bind.dialect.name != "sqlite":
        return

    if not _has_legacy_business_fk_refs(bind):
        return

    # Tabla sombra para satisfacer FKs legacy que quedaron apuntando a business_fkfix_old.
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS business_fkfix_old (
                id INTEGER NOT NULL PRIMARY KEY
            )
            """
        )
    )

    # Sincroniza ids actuales de business.
    op.execute(
        sa.text("INSERT OR IGNORE INTO business_fkfix_old(id) SELECT id FROM business")
    )
    op.execute(
        sa.text(
            "DELETE FROM business_fkfix_old WHERE id NOT IN (SELECT id FROM business)"
        )
    )

    # Triggers para mantener sincronizacion continua de ids.
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_business_shadow_insert"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_business_shadow_delete"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_business_shadow_update"))

    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_business_shadow_insert
            AFTER INSERT ON business
            BEGIN
                INSERT OR IGNORE INTO business_fkfix_old(id) VALUES (NEW.id);
            END
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_business_shadow_delete
            AFTER DELETE ON business
            BEGIN
                DELETE FROM business_fkfix_old WHERE id = OLD.id;
            END
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_business_shadow_update
            AFTER UPDATE OF id ON business
            BEGIN
                DELETE FROM business_fkfix_old WHERE id = OLD.id;
                INSERT OR IGNORE INTO business_fkfix_old(id) VALUES (NEW.id);
            END
            """
        )
    )


def downgrade():
    bind = op.get_bind()

    if bind.dialect.name != "sqlite":
        return

    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_business_shadow_insert"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_business_shadow_delete"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_business_shadow_update"))
    op.execute(sa.text("DROP TABLE IF EXISTS business_fkfix_old"))
