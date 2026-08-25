# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Regression tests for accounting voucher historical metadata."""

from decimal import Decimal
from types import SimpleNamespace

from coati_payroll.nomina_engine.services.accounting_voucher_service import AccountingVoucherService


class _Session:
    def __init__(self, entity):
        self.entity = entity
        self.added = []

    def get(self, *_args):
        return self.entity

    def add(self, line):
        self.added.append(line)


def test_voucher_uses_frozen_concept_accounts_when_catalog_changes():
    """Regenerating a voucher cannot remap historical amounts to new accounts."""
    live_entity = SimpleNamespace(
        contabilizable=True,
        invertir_asiento_contable=False,
        codigo_cuenta_debe="NUEVO-DEBE",
        codigo_cuenta_haber="NUEVO-HABER",
        descripcion_cuenta_debe="Nuevo debe",
        descripcion_cuenta_haber="Nuevo haber",
        nombre="Bono cambiado",
        codigo="BONO",
    )
    session = _Session(live_entity)
    service = AccountingVoucherService(session)
    nomina = SimpleNamespace(
        catalogos_snapshot={
            "percepciones": [
                {
                    "id": "percepcion-1",
                    "codigo": "BONO",
                    "nombre": "Bono histórico",
                    "contabilizable": True,
                    "invertir_asiento_contable": False,
                    "codigo_cuenta_debe": "HIST-DEBE",
                    "descripcion_cuenta_debe": "Gasto histórico",
                    "codigo_cuenta_haber": "HIST-HABER",
                    "descripcion_cuenta_haber": "Pasivo histórico",
                }
            ]
        }
    )
    comprobante = SimpleNamespace(id="comprobante-1")
    empleado = SimpleNamespace(id="empleado-1", codigo_empleado="E-1")
    nomina_empleado = SimpleNamespace(id="ne-1", empleado_id=empleado.id)
    detalle = SimpleNamespace(
        tipo="income",
        percepcion_id="percepcion-1",
        deduccion_id=None,
        prestacion_id=None,
        monto=Decimal("100.00"),
        descripcion="",
        codigo="BONO",
    )

    service._build_concept_lines(
        comprobante, nomina, nomina_empleado, empleado, "Empleado Uno", None, detalle, 0, 0,
        Decimal("0.00"), Decimal("0.00"),
    )

    assert [line.codigo_cuenta for line in session.added] == ["HIST-DEBE", "HIST-HABER"]
