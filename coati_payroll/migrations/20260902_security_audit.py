# SPDX-License-Identifier: Apache-2.0
"""Add authentication and user administration audit events."""

from alembic import op
import sqlalchemy as sa

revision = "20260902_security_audit"
down_revision = "20260902_api_tokens"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("security_audit_log"):
        op.create_table(
            "security_audit_log",
            sa.Column("id", sa.String(26), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("creado", sa.Date(), nullable=False),
            sa.Column("creado_por", sa.String(150), nullable=True),
            sa.Column("modificado", sa.DateTime(), nullable=True),
            sa.Column("modificado_por", sa.String(150), nullable=True),
            sa.Column("event", sa.String(50), nullable=False),
            sa.Column("actor", sa.String(150), nullable=False),
            sa.Column("target_username", sa.String(150), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_security_audit_log_event", "security_audit_log", ["event"])
        op.create_index("ix_security_audit_log_actor", "security_audit_log", ["actor"])


def downgrade():
    if sa.inspect(op.get_bind()).has_table("security_audit_log"):
        op.drop_table("security_audit_log")
