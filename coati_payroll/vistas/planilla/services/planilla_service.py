# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Service for planilla business logic."""

from copy import deepcopy
from typing import Any, cast

from coati_payroll.model import (
    Planilla,
    PlanillaDeduccion,
    PlanillaIngreso,
    PlanillaPrestacion,
    db,
)


class PlanillaService:
    """Service for planilla operations."""

    @staticmethod
    def can_delete(planilla: Planilla) -> tuple[bool, str | None]:
        """Check if a planilla can be deleted.

        Args:
            planilla: The planilla to check

        Returns:
            Tuple of (can_delete, error_message). If can_delete is True, error_message is None.
        """
        if planilla.nominas:
            return False, "No se puede eliminar una planilla con nominas generadas."
        return True, None

    @staticmethod
    def _build_clone_name(base_name: str) -> str:
        """Generate a unique name for a cloned planilla."""
        candidate = f"{base_name} (Copia)"
        counter = 2
        while db.session.execute(db.select(Planilla.id).filter_by(nombre=candidate)).scalar_one_or_none() is not None:
            candidate = f"{base_name} (Copia {counter})"
            counter += 1
        return candidate

    @staticmethod
    def clone_planilla(planilla: Planilla, creado_por: str | None = None) -> Planilla:
        """Clone a planilla and its configured percepciones/deducciones/prestaciones."""
        nueva_planilla = Planilla(
            nombre=PlanillaService._build_clone_name(planilla.nombre),
            descripcion=planilla.descripcion,
            activo=planilla.activo,
            parametros=deepcopy(planilla.parametros) if planilla.parametros else {},
            tipo_planilla_id=planilla.tipo_planilla_id,
            moneda_id=planilla.moneda_id,
            empresa_id=planilla.empresa_id,
            mes_inicio_fiscal=planilla.mes_inicio_fiscal,
            # A planilla-bound vacation policy cannot be shared: the vacation
            # service correctly rejects it when its ``planilla_id`` differs.
            # Cloning its foreign key would therefore create a payroll that
            # fails as soon as vacation processing is enabled. Policies are
            # intentionally configured independently on the clone.
            vacation_policy_id=None,
            periodo_fiscal_inicio=planilla.periodo_fiscal_inicio,
            periodo_fiscal_fin=planilla.periodo_fiscal_fin,
            prioridad_prestamos=planilla.prioridad_prestamos,
            prioridad_adelantos=planilla.prioridad_adelantos,
            aplicar_prestamos_automatico=planilla.aplicar_prestamos_automatico,
            aplicar_adelantos_automatico=planilla.aplicar_adelantos_automatico,
            codigo_cuenta_debe_salario=planilla.codigo_cuenta_debe_salario,
            descripcion_cuenta_debe_salario=planilla.descripcion_cuenta_debe_salario,
            codigo_cuenta_haber_salario=planilla.codigo_cuenta_haber_salario,
            descripcion_cuenta_haber_salario=planilla.descripcion_cuenta_haber_salario,
            creado_por=creado_por,
            creado_por_plugin=False,
            plugin_source=planilla.plugin_source,
        )
        db.session.add(nueva_planilla)
        db.session.flush()

        planilla_percepciones = cast(list[Any], planilla.planilla_percepciones)
        for percepcion in planilla_percepciones:
            db.session.add(
                PlanillaIngreso(
                    planilla_id=nueva_planilla.id,
                    percepcion_id=percepcion.percepcion_id,
                    orden=percepcion.orden,
                    editable=percepcion.editable,
                    monto_predeterminado=percepcion.monto_predeterminado,
                    porcentaje=percepcion.porcentaje,
                    activo=percepcion.activo,
                    creado_por=creado_por,
                )
            )

        planilla_deducciones = cast(list[Any], planilla.planilla_deducciones)
        for deduccion in planilla_deducciones:
            db.session.add(
                PlanillaDeduccion(
                    planilla_id=nueva_planilla.id,
                    deduccion_id=deduccion.deduccion_id,
                    prioridad=deduccion.prioridad,
                    orden=deduccion.orden,
                    editable=deduccion.editable,
                    monto_predeterminado=deduccion.monto_predeterminado,
                    porcentaje=deduccion.porcentaje,
                    activo=deduccion.activo,
                    es_obligatoria=deduccion.es_obligatoria,
                    detener_si_insuficiente=deduccion.detener_si_insuficiente,
                    creado_por=creado_por,
                )
            )

        planilla_prestaciones = cast(list[Any], planilla.planilla_prestaciones)
        for prestacion in planilla_prestaciones:
            db.session.add(
                PlanillaPrestacion(
                    planilla_id=nueva_planilla.id,
                    prestacion_id=prestacion.prestacion_id,
                    orden=prestacion.orden,
                    editable=prestacion.editable,
                    monto_predeterminado=prestacion.monto_predeterminado,
                    porcentaje=prestacion.porcentaje,
                    activo=prestacion.activo,
                    creado_por=creado_por,
                )
            )

        db.session.commit()
        return nueva_planilla
