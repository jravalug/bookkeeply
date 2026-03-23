"""add waste evidence file url to inventory movement

Revision ID: f21d4e5f6a7b
Revises: f20c3d4e5f6a
Create Date: 2026-03-09 20:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f21d4e5f6a7b"
down_revision = "f20c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("waste_evidence_file_url", sa.String(length=255), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("inventory_movement", schema=None) as batch_op:
        batch_op.drop_column("waste_evidence_file_url")
