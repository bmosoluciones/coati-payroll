# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Calculation items - immutable domain models for payroll items."""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple


class DeduccionItem(NamedTuple):
    """Represents a deduction to be applied."""

    codigo: str
    nombre: str
    monto: Decimal
    prioridad: int
    es_obligatoria: bool
    deduccion_id: str | None = None
    tipo: str = "deduccion"  # deduccion, prestamo, adelanto
    monto_exento: Decimal = Decimal("0.00")


class PercepcionItem(NamedTuple):
    """Represents a perception to be applied."""

    codigo: str
    nombre: str
    monto: Decimal
    prioridad: int
    gravable: bool
    percepcion_id: str | None = None
    monto_exento: Decimal = Decimal("0.00")
    monto_gravable: Decimal | None = None


class PrestacionItem(NamedTuple):
    """Represents an employer benefit to be calculated."""

    codigo: str
    nombre: str
    monto: Decimal
    prioridad: int
    prestacion_id: str | None = None
