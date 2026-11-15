import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("submission_id", sa.UUID(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("attempts >= 0"),
    )
    op.create_index("outbox_pending_idx", "outbox_events", ["available_at", "submission_id"], postgresql_where=sa.text("processed_at IS NULL"))


def downgrade() -> None:
    op.drop_table("outbox_events")
