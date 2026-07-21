# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Helper services for implementation utilities."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_

from coati_payroll.model import Deduccion, Empresa, Percepcion, Prestacion, VacationPolicy, db

EXPECTED_HEADERS = [
    "type",
    "id",
    "debit account",
    "debit account description",
    "credit account",
    "credit account description",
]


@dataclass
class BulkAccountingImportResult:
    """Result for accounting account bulk import operation."""

    updated_rows: int = 0
    skipped_rows: int = 0


def _normalize(value: object) -> str:
    return str(value or "").strip()


def _find_company(visible_id: str) -> Empresa | None:
    normalized = visible_id.strip()
    lowered = normalized.lower()
    return db.session.execute(
        db.select(Empresa).where(
            or_(
                func.lower(Empresa.razon_social) == lowered,
                func.lower(Empresa.nombre_comercial) == lowered,
                func.lower(Empresa.codigo) == lowered,
            )
        )
    ).scalar_one_or_none()


def _find_by_name_or_code(
    model: type[Percepcion] | type[Deduccion] | type[Prestacion] | type[VacationPolicy], visible_id: str
):
    lowered = visible_id.strip().lower()
    return db.session.execute(
        db.select(model).where(or_(func.lower(model.nombre) == lowered, func.lower(model.codigo) == lowered))
    ).scalar_one_or_none()


ACCOUNT_FIELDS = {
    "company": (
        "codigo_cuenta_debe_salario",
        "descripcion_cuenta_debe_salario",
        "codigo_cuenta_haber_salario",
        "descripcion_cuenta_haber_salario",
    ),
    "earnings": ("codigo_cuenta_debe", "descripcion_cuenta_debe", "codigo_cuenta_haber", "descripcion_cuenta_haber"),
    "deductions": ("codigo_cuenta_debe", "descripcion_cuenta_debe", "codigo_cuenta_haber", "descripcion_cuenta_haber"),
    "benefits": ("codigo_cuenta_debe", "descripcion_cuenta_debe", "codigo_cuenta_haber", "descripcion_cuenta_haber"),
    "vacation_policy": (
        "cuenta_debito_vacaciones_pagadas",
        "descripcion_cuenta_debito_vacaciones_pagadas",
        "cuenta_credito_vacaciones_pagadas",
        "descripcion_cuenta_credito_vacaciones_pagadas",
    ),
}

ENTITY_LOOKUPS = {
    "company": _find_company,
    "earnings": lambda visible_id: _find_by_name_or_code(Percepcion, visible_id),
    "deductions": lambda visible_id: _find_by_name_or_code(Deduccion, visible_id),
    "benefits": lambda visible_id: _find_by_name_or_code(Prestacion, visible_id),
    "vacation_policy": lambda visible_id: _find_by_name_or_code(VacationPolicy, visible_id),
}


def _validate_headers(header_row: list[str]) -> None:
    normalized_headers = [_normalize(value).lower() for value in header_row]
    if normalized_headers != EXPECTED_HEADERS:
        raise ValueError("Formato inválido. Verifique los encabezados de la plantilla de configuración contable.")


def import_accounting_configuration_rows(rows: list[list[object]]) -> BulkAccountingImportResult:
    """Import accounting account configuration from parsed worksheet rows."""
    if not rows:
        raise ValueError("La planilla está vacía.")

    _validate_headers([str(cell or "") for cell in rows[0]])

    result = BulkAccountingImportResult()

    for row in rows[1:]:
        normalized_row = [_normalize(cell) for cell in row]
        if len(normalized_row) < 6:
            normalized_row.extend([""] * (6 - len(normalized_row)))

        row_type, visible_id, *_ = normalized_row[:6]

        if not any(normalized_row):
            continue

        if not row_type or not visible_id:
            result.skipped_rows += 1
            continue

        row_type = row_type.lower()
        lookup = ENTITY_LOOKUPS.get(row_type)
        fields = ACCOUNT_FIELDS.get(row_type)
        if lookup is None or fields is None:
            result.skipped_rows += 1
            continue

        entity = lookup(visible_id)
        if not entity:
            result.skipped_rows += 1
            continue
        for field, value in zip(fields, normalized_row[2:6]):
            setattr(entity, field, value)

        result.updated_rows += 1

    db.session.commit()
    return result
