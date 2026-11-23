"""add push subscriptions

Revision ID: c4a8e1b9d270
Revises: d2fe9905f72b
Create Date: 2026-11-23 01:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a8e1b9d270"
down_revision: Union[str, Sequence[str], None] = "d2fe9905f72b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("endpoint", sa.Text(), nullable=True),
        sa.Column("p256dh", sa.Text(), nullable=True),
        sa.Column("auth", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index(op.f("ix_push_subscriptions_id"), "push_subscriptions", ["id"], unique=False)
    op.create_index(op.f("ix_push_subscriptions_user_email"), "push_subscriptions", ["user_email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_push_subscriptions_user_email"), table_name="push_subscriptions")
    op.drop_index(op.f("ix_push_subscriptions_id"), table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
