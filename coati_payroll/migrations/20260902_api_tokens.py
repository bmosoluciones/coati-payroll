# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Add hashed bearer tokens for the integration API."""

from alembic import op
import sqlalchemy as sa

revision = "20260902_api_tokens"
down_revision = "20260902_liquidacion_accounting"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("api_token"):
        op.create_table(
            "api_token",
            sa.Column("id", sa.String(26), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("creado", sa.Date(), nullable=False),
            sa.Column("creado_por", sa.String(150), nullable=True),
            sa.Column("modificado", sa.DateTime(), nullable=True),
            sa.Column("modificado_por", sa.String(150), nullable=True),
            sa.Column("usuario_id", sa.String(26), nullable=False),
            sa.Column("nombre", sa.String(100), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("alcances", sa.JSON(), nullable=True),
            sa.Column("expira_en", sa.DateTime(), nullable=True),
            sa.Column("ultimo_uso_en", sa.DateTime(), nullable=True),
            sa.Column("revocado_en", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_api_token_hash"),
        )
        op.create_index("ix_api_token_usuario_id", "api_token", ["usuario_id"])
        op.create_index("ix_api_token_token_hash", "api_token", ["token_hash"])
        op.create_index("ix_api_token_expira_en", "api_token", ["expira_en"])


def downgrade():
    if sa.inspect(op.get_bind()).has_table("api_token"):
        op.drop_table("api_token")
