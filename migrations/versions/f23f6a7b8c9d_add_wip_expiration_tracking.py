"""add wip expiration tracking

Revision ID: f23f6a7b8c9d
Revises: f22e5f6a7b8c
Create Date: 2026-03-09 22:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f23f6a7b8c9d"
down_revision = "f22e5f6a7b8c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "inventory_wip_balance",
        sa.Column("expiration_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "inventory_wip_balance",
        sa.Column("expiration_source", sa.String(length=30), nullable=True),
    )


def downgrade():
    op.drop_column("inventory_wip_balance", "expiration_source")
    op.drop_column("inventory_wip_balance", "expiration_date")
