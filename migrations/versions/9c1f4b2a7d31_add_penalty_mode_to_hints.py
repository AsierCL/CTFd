"""Add penalty_mode to Hints

Revision ID: 9c1f4b2a7d31
Revises: a3e1c5d7b9f2
Create Date: 2026-10-23 00:00:00.000000

"""

from alembic import op  # noqa: I001
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c1f4b2a7d31"
down_revision = "a3e1c5d7b9f2"
branch_labels = None
depends_on = None


def upgrade():
    # NULL means "inherit the instance setting", so existing hints are untouched
    op.add_column(
        "hints", sa.Column("penalty_mode", sa.String(length=32), nullable=True)
    )


def downgrade():
    op.drop_column("hints", "penalty_mode")
