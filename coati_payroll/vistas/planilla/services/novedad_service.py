# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Service for novedad business logic."""

from decimal import Decimal
from typing import Any, cast
from flask import has_request_context, request

from coati_payroll.absence_defaults import (
    resolve_absence_flags,
    resolve_explicit_flag_from_form,
)
from coati_payroll.model import db, Planilla, Nomina, NominaNovedad, Percepcion, Deduccion
from coati_payroll.vistas.planilla.helpers.form_helpers import get_concepto_ids_from_form


class NovedadService:
    """Service for novedad operations."""

    @staticmethod
    def _resolve_explicit_flag_from_form(form, field_name: str) -> bool | None:
        """Get explicit boolean value from form if provided in request payload.

        Returns None when the field is not present in the payload, so the caller
        can apply concept-level defaults.
        """
        return resolve_explicit_flag_from_form(
            form,
            field_name,
            has_request_context=has_request_context(),
            request_form=request.form if has_request_context() else None,
        )

    @staticmethod
    def resolve_absence_flags(
        percepcion_id: str | None,
        deduccion_id: str | None,
        explicit_es_inasistencia: bool | None = None,
        explicit_descontar_pago_inasistencia: bool | None = None,
    ) -> tuple[bool, bool]:
        """Resolve absence flags with concept-level defaults when not explicitly provided."""
        return resolve_absence_flags(
            percepcion_id=percepcion_id,
            deduccion_id=deduccion_id,
            get_percepcion=lambda concept_id: db.session.get(Percepcion, concept_id),
            get_deduccion=lambda concept_id: db.session.get(Deduccion, concept_id),
            explicit_es_inasistencia=explicit_es_inasistencia,
            explicit_descontar_pago_inasistencia=explicit_descontar_pago_inasistencia,
        )

    @staticmethod
    def listar_novedades(planilla: Planilla, nomina: Nomina) -> list:
        """List all novedades for a nomina.

        Args:
            planilla: The planilla
            nomina: The nomina

        Returns:
            List of NominaNovedad objects
        """
        # Get all employees in this planilla
        planilla_empleados = cast(list[Any], planilla.planilla_empleados)
        empleado_ids = [pe.empleado_id for pe in planilla_empleados if pe.activo]

        # Query novedades that belong to this specific nomina, or floating novelties
        # (nomina_id is None) whose date falls within the period, and are for employees in this planilla.
        from sqlalchemy import or_, and_

        condition = or_(
            NominaNovedad.nomina_id == nomina.id,
            and_(
                NominaNovedad.nomina_id.is_(None),
                NominaNovedad.fecha_novedad >= nomina.periodo_inicio,
                NominaNovedad.fecha_novedad <= nomina.periodo_fin,
            )
        )

        novedades = (
            db.session.execute(
                db.select(NominaNovedad)
                .filter(
                    NominaNovedad.empleado_id.in_(empleado_ids),
                    condition,
                )
                .order_by(NominaNovedad.fecha_novedad.desc(), NominaNovedad.timestamp.desc())
            )
            .scalars()
            .all()
        )

        return cast(list[Any], novedades)

    @staticmethod
    def validar_fecha_novedad(fecha_novedad, nomina: Nomina) -> tuple[bool, str | None]:
        """Validate that fecha_novedad falls within the nomina period.

        Args:
            fecha_novedad: The date to validate
            nomina: The nomina

        Returns:
            Tuple of (is_valid, error_message)
        """
        from coati_payroll.i18n import _

        if fecha_novedad:
            if fecha_novedad < nomina.periodo_inicio or fecha_novedad > nomina.periodo_fin:
                return False, _("La fecha de la novedad debe estar dentro del período de la nómina ({} a {}).").format(
                    nomina.periodo_inicio.strftime("%d/%m/%Y"),
                    nomina.periodo_fin.strftime("%d/%m/%Y"),
                )
        return True, None

    @staticmethod
    def crear_novedad(nomina: Nomina, form, usuario: str) -> NominaNovedad:
        """Create a new novedad.

        Args:
            nomina: The nomina
            form: The form with novedad data
            usuario: Username of the user creating

        Returns:
            The created NominaNovedad
        """
        percepcion_id, deduccion_id = get_concepto_ids_from_form(form)
        explicit_es_inasistencia = NovedadService._resolve_explicit_flag_from_form(form, "es_inasistencia")
        explicit_descontar_pago = NovedadService._resolve_explicit_flag_from_form(form, "descontar_pago_inasistencia")
        es_inasistencia, descontar_pago_inasistencia = NovedadService.resolve_absence_flags(
            percepcion_id=percepcion_id,
            deduccion_id=deduccion_id,
            explicit_es_inasistencia=explicit_es_inasistencia,
            explicit_descontar_pago_inasistencia=explicit_descontar_pago,
        )

        novedad = NominaNovedad(
            nomina_id=nomina.id,
            empleado_id=form.empleado_id.data,
            codigo_concepto=form.codigo_concepto.data,
            tipo_valor=form.tipo_valor.data,
            valor_cantidad=Decimal(str(form.valor_cantidad.data)),
            fecha_novedad=form.fecha_novedad.data,
            percepcion_id=percepcion_id,
            deduccion_id=deduccion_id,
            es_inasistencia=es_inasistencia,
            descontar_pago_inasistencia=descontar_pago_inasistencia,
            creado_por=usuario,
        )
        db.session.add(novedad)
        db.session.commit()
        return novedad

    @staticmethod
    def actualizar_novedad(novedad: NominaNovedad, form, usuario: str):
        """Update an existing novedad.

        Args:
            novedad: The novedad to update
            form: The form with updated data
            usuario: Username of the user updating
        """
        percepcion_id, deduccion_id = get_concepto_ids_from_form(form)
        explicit_es_inasistencia = NovedadService._resolve_explicit_flag_from_form(form, "es_inasistencia")
        explicit_descontar_pago = NovedadService._resolve_explicit_flag_from_form(form, "descontar_pago_inasistencia")
        es_inasistencia, descontar_pago_inasistencia = NovedadService.resolve_absence_flags(
            percepcion_id=percepcion_id,
            deduccion_id=deduccion_id,
            explicit_es_inasistencia=explicit_es_inasistencia,
            explicit_descontar_pago_inasistencia=explicit_descontar_pago,
        )

        novedad.empleado_id = form.empleado_id.data
        novedad.codigo_concepto = form.codigo_concepto.data
        novedad.tipo_valor = form.tipo_valor.data
        novedad.valor_cantidad = Decimal(str(form.valor_cantidad.data))
        novedad.fecha_novedad = form.fecha_novedad.data
        novedad.percepcion_id = percepcion_id
        novedad.deduccion_id = deduccion_id
        novedad.es_inasistencia = es_inasistencia
        novedad.descontar_pago_inasistencia = descontar_pago_inasistencia
        novedad.modificado_por = usuario
        db.session.commit()
