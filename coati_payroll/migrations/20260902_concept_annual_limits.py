# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Add annual ceilings and exempt amounts to payroll concepts."""

from alembic import op
import sqlalchemy as sa

revision = "20260902_concept_annual_limits"
down_revision = "20260902_user_locale"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table_name in ("percepcion", "deduccion"):
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in ("techo_anual", "tope_base_gravable", "monto_exento"):
            if column_name not in columns:
                op.add_column(table_name, sa.Column(column_name, sa.Numeric(14, 2), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table_name in ("percepcion", "deduccion"):
        if inspector.has_table(table_name):
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name in ("monto_exento", "tope_base_gravable", "techo_anual"):
                if column_name in columns:
                    op.drop_column(table_name, column_name)
