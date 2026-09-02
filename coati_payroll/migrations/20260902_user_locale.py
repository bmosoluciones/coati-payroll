# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Add an optional per-user language preference."""

from alembic import op
import sqlalchemy as sa


revision = "20260902_user_locale"
down_revision = "20260902_auth_email_security"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("usuario") and not any(c["name"] == "idioma" for c in inspector.get_columns("usuario")):
        op.add_column("usuario", sa.Column("idioma", sa.String(length=10), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("usuario") and any(c["name"] == "idioma" for c in inspector.get_columns("usuario")):
        op.drop_column("usuario", "idioma")
