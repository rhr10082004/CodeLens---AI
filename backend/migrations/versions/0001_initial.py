"""Create CodeLens account and analysis tables.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_analyses_user_created", "analyses", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_analyses_user_created", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
