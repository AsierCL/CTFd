"""Rename hints.penalty_mode to cost_behavior and tie awards to challenges

Revision ID: c4a7f1d9b2e8
Revises: 9c1f4b2a7d31
Create Date: 2026-10-23 00:00:00.000000

"""

from alembic import op  # noqa: I001
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4a7f1d9b2e8"
down_revision = "9c1f4b2a7d31"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "hints",
        "penalty_mode",
        new_column_name="cost_behavior",
        existing_type=sa.String(length=32),
        existing_nullable=True,
    )
    # No foreign key on purpose: SQLite cannot add a constraint to an existing table
    # without rebuilding it, and CTFd supports SQLite. Cleanup is explicit where
    # solves and submissions are already removed.
    op.add_column("awards", sa.Column("challenge_id", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("awards", "challenge_id")
    op.alter_column(
        "hints",
        "cost_behavior",
        new_column_name="penalty_mode",
        existing_type=sa.String(length=32),
        existing_nullable=True,
    )
