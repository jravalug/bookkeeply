"""add typed waste fields to inventory movement

Revision ID: f19b2c3d4e5f
Revises: f08a9b0c1d2e
Create Date: 2026-03-09 20:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f19b2c3d4e5f"
down_revision = "f08a9b0c1d2e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("waste_reason", sa.String(length=40), nullable=True)
        )
        batch_op.add_column(
            sa.Column("waste_responsible", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(sa.Column("waste_evidence", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.drop_column("waste_evidence")
        batch_op.drop_column("waste_responsible")
        batch_op.drop_column("waste_reason")
