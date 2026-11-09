"""Redact evidence for analyses whose source was not retained."""

import json

from alembic import op
import sqlalchemy as sa

from app.retention import redact_finding_evidence

revision = "0002_redact_unretained_evidence"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    analyses = sa.table(
        "analyses",
        sa.column("id", sa.Integer),
        sa.column("source_code", sa.Text),
        sa.column("result_json", sa.Text),
    )
    rows = connection.execute(
        sa.select(analyses.c.id, analyses.c.result_json).where(
            sa.or_(analyses.c.source_code == "", analyses.c.source_code.is_(None))
        )
    )
    for analysis_id, result_json in rows:
        result = json.loads(result_json)
        redacted = redact_finding_evidence(result)
        if redacted != result:
            connection.execute(
                sa.update(analyses)
                .where(analyses.c.id == analysis_id)
                .values(result_json=json.dumps(redacted))
            )


def downgrade() -> None:
    """Evidence redaction is irreversible; do not restore sensitive snippets."""
