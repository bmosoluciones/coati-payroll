# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Add configurable liquidation rules, payment traceability and vouchers."""

from alembic import op
import sqlalchemy as sa


revision = "20260902_liquidacion_accounting"
down_revision = "20260902_concept_annual_limits"
branch_labels = None
depends_on = None


def _columns(table):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("liquidacion_concepto"):
        columns = _columns("liquidacion_concepto")
        for name, column in (("jurisdiccion", sa.String(100)), ("esquema_json", sa.JSON())):
            if name not in columns:
                op.add_column("liquidacion_concepto", sa.Column(name, column, nullable=True))
    if inspector.has_table("liquidacion"):
        columns = _columns("liquidacion")
        additions = {
            "causa_terminacion": sa.String(100), "medio_pago": sa.String(40),
            "referencia_pago": sa.String(150), "fecha_pago": sa.Date(), "detalle_pago": sa.JSON(),
        }
        for name, column in additions.items():
            if name not in columns:
                op.add_column("liquidacion", sa.Column(name, column, nullable=True))
    if inspector.has_table("comprobante_contable"):
        columns = _columns("comprobante_contable")
        if "liquidacion_id" not in columns or "nomina_id" in columns:
            with op.batch_alter_table("comprobante_contable", recreate="always") as batch:
                if "nomina_id" in columns:
                    batch.alter_column("nomina_id", existing_type=sa.String(26), nullable=True)
                if "liquidacion_id" not in columns:
                    batch.add_column(sa.Column("liquidacion_id", sa.String(26), nullable=True))
                    batch.create_foreign_key("fk_comprobante_liquidacion", "liquidacion", ["liquidacion_id"], ["id"])
                    batch.create_unique_constraint("uq_comprobante_liquidacion", ["liquidacion_id"])
    if inspector.has_table("comprobante_contable_linea"):
        columns = _columns("comprobante_contable_linea")
        if "nomina_empleado_id" in columns:
            with op.batch_alter_table("comprobante_contable_linea") as batch:
                batch.alter_column("nomina_empleado_id", existing_type=sa.String(26), nullable=True)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("comprobante_contable") and "liquidacion_id" in _columns("comprobante_contable"):
        with op.batch_alter_table("comprobante_contable", recreate="always") as batch:
            batch.drop_constraint("uq_comprobante_liquidacion", type_="unique")
            batch.drop_constraint("fk_comprobante_liquidacion", type_="foreignkey")
            batch.drop_column("liquidacion_id")
    for name in ("detalle_pago", "fecha_pago", "referencia_pago", "medio_pago", "causa_terminacion"):
        if inspector.has_table("liquidacion") and name in _columns("liquidacion"):
            op.drop_column("liquidacion", name)
    for name in ("esquema_json", "jurisdiccion"):
        if inspector.has_table("liquidacion_concepto") and name in _columns("liquidacion_concepto"):
            op.drop_column("liquidacion_concepto", name)
