import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.String(2048), nullable=False, server_default=""),
        sa.Column("professor_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "student_ids",
            postgresql.ARRAY(sa.BigInteger()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="DRAFT"),
        *timestamps(),
        sa.CheckConstraint("professor_id >= 0"),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','COMPLETED','ARCHIVED')"),
    )
    op.create_table(
        "assignments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.String(2048), nullable=False, server_default=""),
        *timestamps(),
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "assignment_id",
            sa.UUID(),
            sa.ForeignKey("assignments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("solution", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="SUBMITTED"),
        *timestamps(),
        sa.CheckConstraint("student_id >= 0"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 10"),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','PENDING','PROCESSING','COMPLETED','FAILED')"
        ),
        sa.UniqueConstraint("assignment_id", "student_id", "attempt"),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.UUID(),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("professor_id", sa.BigInteger(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        *timestamps(),
        sa.CheckConstraint("grade BETWEEN 0 AND 100"),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.UUID(),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("size >= 0"),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("operation", sa.Text(), primary_key=True),
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "courses_created_idx", "courses", [sa.text("created_at DESC"), "id"]
    )
    op.create_index("assignments_course_idx", "assignments", ["course_id"])
    op.create_index("assignments_created_idx", "assignments", ["created_at", "id"])
    op.create_index(
        "submissions_created_idx", "submissions", [sa.text("created_at DESC"), "id"]
    )
    op.create_index("artifacts_submission_idx", "artifacts", ["submission_id"])


def downgrade() -> None:
    for table in (
        "idempotency_keys",
        "artifacts",
        "reviews",
        "submissions",
        "assignments",
        "courses",
    ):
        op.drop_table(table)
