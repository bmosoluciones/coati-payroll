# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Repository for Novelty operations."""

from __future__ import annotations

from datetime import date

from coati_payroll.model import NominaNovedad

from .base_repository import BaseRepository


class NoveltyRepository(BaseRepository[NominaNovedad]):
    """Repository for NominaNovedad operations."""

    def get_by_id(self, novelty_id: str) -> NominaNovedad | None:
        """Get novelty by ID."""
        return self.session.get(NominaNovedad, novelty_id)

    def get_by_employee_and_period(
        self, empleado_id: str, periodo_inicio: date, periodo_fin: date, nomina_id: str | None = None
    ) -> list[NominaNovedad]:
        """Get novelties for employee within period, filtering by specific nomina if provided."""
        from sqlalchemy import and_, or_, select

        stmt = select(NominaNovedad).filter(NominaNovedad.empleado_id == empleado_id)

        if nomina_id:
            condition = or_(
                NominaNovedad.nomina_id == nomina_id,
                and_(
                    NominaNovedad.nomina_id.is_(None),
                    NominaNovedad.fecha_novedad >= periodo_inicio,
                    NominaNovedad.fecha_novedad <= periodo_fin,
                ),
            )
            stmt = stmt.filter(condition)
        else:
            stmt = stmt.filter(
                NominaNovedad.fecha_novedad >= periodo_inicio,
                NominaNovedad.fecha_novedad <= periodo_fin,
            )

        return list(self.session.execute(stmt).unique().scalars().all())

    def save(self, novelty: NominaNovedad) -> NominaNovedad:
        """Save novelty."""
        self.session.add(novelty)
        return novelty
