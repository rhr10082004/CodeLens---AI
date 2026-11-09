"""Add server-side access-token revocation."""

from alembic import op
import sqlalchemy as sa

revision = "0003_revoked_access_tokens"
down_revision = "0002_redact_unretained_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revoked_access_tokens",
        sa.Column("token_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_revoked_access_tokens_expires_at",
        "revoked_access_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_revoked_access_tokens_expires_at", table_name="revoked_access_tokens")
    op.drop_table("revoked_access_tokens")
