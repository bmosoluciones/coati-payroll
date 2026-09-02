# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Helper functions for audit and governance of payroll concepts."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import true

from coati_payroll.enums import EstadoAprobacion, TipoUsuario, NominaEstado
from coati_payroll.model import (
    ConceptoAuditLog,
    PlanillaAuditLog,
    NominaAuditLog,
    ReglaCalculoAuditLog,
    SecurityAuditLog,
    Percepcion,
    Deduccion,
    Prestacion,
    Planilla,
    Nomina,
    ReglaCalculo,
    db,
    utc_now,
)


def registrar_evento_seguridad(
    evento: str,
    actor: str,
    *,
    objetivo: str | None = None,
    exito: bool = True,
    detalles: Optional[Dict[str, Any]] = None,
) -> SecurityAuditLog:
    """Record an authentication or user-administration event."""
    from flask import has_request_context, request

    entry = SecurityAuditLog(
        event=evento,
        actor=actor,
        target_username=objetivo,
        success=exito,
        ip_address=request.remote_addr if has_request_context() else None,
        user_agent=(request.user_agent.string[:500] if has_request_context() else None),
        details=detalles or {},
    )
    db.session.add(entry)
    return entry


def puede_aprobar_concepto(usuario_tipo: str) -> bool:
    """Check if user can approve payroll concepts.

    Only ADMIN and HHRR users can approve percepciones, deducciones, and prestaciones.

    Args:
        usuario_tipo: User type (admin, hhrr, audit)

    Returns:
        True if user can approve concepts, False otherwise
    """
    return usuario_tipo in [TipoUsuario.ADMIN, TipoUsuario.HHRR]


def crear_log_auditoria(
    concepto: Percepcion | Deduccion | Prestacion,
    accion: str,
    usuario: str,
    descripcion: Optional[str] = None,
    cambios: Optional[Dict[str, Any]] = None,
    estado_anterior: Optional[str] = None,
    estado_nuevo: Optional[str] = None,
) -> ConceptoAuditLog:
    """Create an audit log entry for a payroll concept change.

    Args:
        concepto: The concept that was changed (Percepcion, Deduccion, or Prestacion)
        accion: Action performed (created, updated, approved, rejected, etc.)
        usuario: Username who performed the action
        descripcion: Human-readable description of the change
        cambios: Dictionary of field-level changes {field: {old: value, new: value}}
        estado_anterior: Previous approval status
        estado_nuevo: New approval status

    Returns:
        The created audit log entry
    """
    # Determine concept type
    if isinstance(concepto, Percepcion):
        tipo_concepto = "percepcion"
        percepcion_id = concepto.id
        deduccion_id = None
        prestacion_id = None
    elif isinstance(concepto, Deduccion):
        tipo_concepto = "deduction"
        percepcion_id = None
        deduccion_id = concepto.id
        prestacion_id = None
    elif isinstance(concepto, Prestacion):
        tipo_concepto = "benefit"
        percepcion_id = None
        deduccion_id = None
        prestacion_id = concepto.id
    else:
        raise ValueError(f"Invalid concept type: {type(concepto)}")

    # Create audit log entry
    log = ConceptoAuditLog(
        tipo_concepto=tipo_concepto,
        percepcion_id=percepcion_id,
        deduccion_id=deduccion_id,
        prestacion_id=prestacion_id,
        accion=accion,
        usuario=usuario,
        descripcion=descripcion,
        cambios=cambios or {},
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
    )

    db.session.add(log)
    return log


def generar_descripcion_cambios(cambios: Dict[str, Any]) -> str:
    """Generate a human-readable description of changes.

    Args:
        cambios: Dictionary of field-level changes

    Returns:
        Human-readable description
    """
    if not cambios:
        return ""

    descripciones = []
    for campo, valores in cambios.items():
        old_val = valores.get("old", "")
        new_val = valores.get("new", "")

        # Format field name
        campo_legible = campo.replace("_", " ").title()

        if old_val == "" or old_val is None:
            descripciones.append(f"{campo_legible} establecido a {new_val}")
        elif new_val == "" or new_val is None:
            descripciones.append(f"{campo_legible} eliminado (era {old_val})")
        else:
            descripciones.append(f"{campo_legible} cambió de {old_val} a {new_val}")

    return "; ".join(descripciones)


def aprobar_concepto(
    concepto: Percepcion | Deduccion | Prestacion,
    usuario: str,
) -> bool:
    """Approve a payroll concept.

    Changes status from 'draft' to 'approved' and records approval information.

    Args:
        concepto: The concept to approve
        usuario: Username who is approving

    Returns:
        True if approved successfully, False if already approved or invalid
    """
    if concepto.estado_aprobacion == EstadoAprobacion.APROBADO:
        return False

    estado_anterior = concepto.estado_aprobacion
    concepto.estado_aprobacion = EstadoAprobacion.APROBADO
    concepto.aprobado_por = usuario
    concepto.aprobado_en = utc_now()

    # Create audit log
    tipo_concepto = type(concepto).__name__.lower()
    crear_log_auditoria(
        concepto=concepto,
        accion="approved",
        usuario=usuario,
        descripcion=f"Aprobó {tipo_concepto} '{concepto.nombre}' (código: {concepto.codigo})",
        estado_anterior=estado_anterior,
        estado_nuevo=EstadoAprobacion.APROBADO,
    )

    return True


def rechazar_concepto(
    concepto: Percepcion | Deduccion | Prestacion,
    usuario: str,
    razon: Optional[str] = None,
) -> bool:
    """Reject a payroll concept (keep as draft).

    Args:
        concepto: The concept to reject
        usuario: Username who is rejecting
        razon: Reason for rejection

    Returns:
        True if rejected successfully
    """
    estado_anterior = concepto.estado_aprobacion
    concepto.estado_aprobacion = EstadoAprobacion.BORRADOR
    concepto.aprobado_por = None
    concepto.aprobado_en = None

    # Create audit log
    tipo_concepto = type(concepto).__name__.lower()
    descripcion = f"Rechazó {tipo_concepto} '{concepto.nombre}' (código: {concepto.codigo})"
    if razon:
        descripcion += f" - Razón: {razon}"

    crear_log_auditoria(
        concepto=concepto,
        accion="rejected",
        usuario=usuario,
        descripcion=descripcion,
        estado_anterior=estado_anterior,
        estado_nuevo=EstadoAprobacion.BORRADOR,
    )

    return True


def marcar_como_borrador_si_editado(
    concepto: Percepcion | Deduccion | Prestacion,
    usuario: str,
    cambios: Dict[str, Any],
) -> None:
    """Mark concept as draft if it was edited while approved.

    When an approved concept is edited, it must return to draft status
    unless it was created by a plugin.

    Args:
        concepto: The concept that was edited
        usuario: Username who edited
        cambios: Dictionary of changes made
    """
    # Don't change status if created by plugin
    if concepto.creado_por_plugin:
        return

    # If currently approved, mark as draft
    if concepto.estado_aprobacion == EstadoAprobacion.APROBADO:
        estado_anterior = concepto.estado_aprobacion
        concepto.estado_aprobacion = EstadoAprobacion.BORRADOR
        concepto.aprobado_por = None
        concepto.aprobado_en = None

        # Create audit log
        tipo_concepto = type(concepto).__name__.lower()
        descripcion_cambios = generar_descripcion_cambios(cambios)

        crear_log_auditoria(
            concepto=concepto,
            accion="updated",
            usuario=usuario,
            descripcion=f"Editó {tipo_concepto} '{concepto.nombre}' - {descripcion_cambios}."
            + " Estado cambiado a borrador.",
            cambios=cambios,
            estado_anterior=estado_anterior,
            estado_nuevo=EstadoAprobacion.BORRADOR,
        )


def detectar_cambios(concepto_original: Dict[str, Any], concepto_nuevo: Dict[str, Any]) -> Dict[str, Any]:
    """Detect changes between original and new concept data.

    Args:
        concepto_original: Original concept data
        concepto_nuevo: New concept data

    Returns:
        Dictionary of changes {field: {old: value, new: value}}
    """
    cambios = {}

    # Fields to track
    campos_importantes = [
        "nombre",
        "descripcion",
        "codigo",
        "formula_tipo",
        "monto_default",
        "porcentaje",
        "base_calculo",
        "gravable",
        "recurrente",
        "activo",
        "codigo_cuenta_debe",
        "codigo_cuenta_haber",
        "tipo",
        "es_impuesto",
        "antes_impuesto",
        "tipo_acumulacion",
        "tope_aplicacion",
    ]

    for campo in campos_importantes:
        if campo in concepto_original and campo in concepto_nuevo:
            old_val = concepto_original[campo]
            new_val = concepto_nuevo[campo]

            # Compare values (handle None and empty strings as equivalent)
            if (old_val or "") != (new_val or ""):
                cambios[campo] = {"old": old_val, "new": new_val}

    return cambios


def obtener_conceptos_en_borrador(planilla_id: str) -> Dict[str, list]:
    """Get all draft concepts associated with a planilla.

    Args:
        planilla_id: ID of the planilla

    Returns:
        Dictionary with lists of draft percepciones, deducciones, and prestaciones
    """
    from coati_payroll.model import PlanillaIngreso, PlanillaDeduccion, PlanillaPrestacion

    # Get draft percepciones
    percepciones_borrador = (
        db.session.query(Percepcion)
        .join(PlanillaIngreso)
        .filter(
            PlanillaIngreso.planilla_id == planilla_id,
            Percepcion.estado_aprobacion == EstadoAprobacion.BORRADOR,
            Percepcion.activo.is_(true()),
        )
        .all()
    )

    # Get draft deducciones
    deducciones_borrador = (
        db.session.query(Deduccion)
        .join(PlanillaDeduccion)
        .filter(
            PlanillaDeduccion.planilla_id == planilla_id,
            Deduccion.estado_aprobacion == EstadoAprobacion.BORRADOR,
            Deduccion.activo.is_(true()),
        )
        .all()
    )

    # Get draft prestaciones
    prestaciones_borrador = (
        db.session.query(Prestacion)
        .join(PlanillaPrestacion)
        .filter(
            PlanillaPrestacion.planilla_id == planilla_id,
            Prestacion.estado_aprobacion == EstadoAprobacion.BORRADOR,
            Prestacion.activo.is_(true()),
        )
        .all()
    )

    return {
        "percepciones": percepciones_borrador,
        "deducciones": deducciones_borrador,
        "prestaciones": prestaciones_borrador,
    }


def tiene_conceptos_en_borrador(planilla_id: str) -> bool:
    """Check if a planilla has any draft concepts.

    Args:
        planilla_id: ID of the planilla

    Returns:
        True if there are any draft concepts, False otherwise
    """
    conceptos = obtener_conceptos_en_borrador(planilla_id)
    return bool(conceptos["percepciones"] or conceptos["deducciones"] or conceptos["prestaciones"])


# ============================================================================
# PLANILLA AUDIT FUNCTIONS
# ============================================================================


def crear_log_auditoria_planilla(
    planilla: Planilla,
    accion: str,
    usuario: str,
    descripcion: Optional[str] = None,
    cambios: Optional[Dict[str, Any]] = None,
    estado_anterior: Optional[str] = None,
    estado_nuevo: Optional[str] = None,
) -> PlanillaAuditLog:
    """Create an audit log entry for a planilla change.

    Args:
        planilla: The planilla that was changed
        accion: Action performed (created, updated, approved, rejected, etc.)
        usuario: Username who performed the action
        descripcion: Human-readable description of the change
        cambios: Dictionary of field-level changes
        estado_anterior: Previous approval status
        estado_nuevo: New approval status

    Returns:
        The created audit log entry
    """
    log = PlanillaAuditLog(
        planilla_id=planilla.id,
        accion=accion,
        usuario=usuario,
        descripcion=descripcion,
        cambios=cambios or {},
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
    )

    db.session.add(log)
    return log


def aprobar_planilla(planilla: Planilla, usuario: str) -> bool:
    """Approve a planilla.

    Changes status from 'draft' to 'approved' and records approval information.

    Args:
        planilla: The planilla to approve
        usuario: Username who is approving

    Returns:
        True if approved successfully, False if already approved or invalid
    """
    if planilla.estado_aprobacion == EstadoAprobacion.APROBADO:
        return False

    estado_anterior = planilla.estado_aprobacion
    planilla.estado_aprobacion = EstadoAprobacion.APROBADO
    planilla.aprobado_por = usuario
    planilla.aprobado_en = utc_now()

    # Create audit log
    crear_log_auditoria_planilla(
        planilla=planilla,
        accion="approved",
        usuario=usuario,
        descripcion=f"Aprobó planilla '{planilla.nombre}'",
        estado_anterior=estado_anterior,
        estado_nuevo=EstadoAprobacion.APROBADO,
    )

    return True


def rechazar_planilla(planilla: Planilla, usuario: str, razon: Optional[str] = None) -> bool:
    """Reject a planilla (keep as draft).

    Args:
        planilla: The planilla to reject
        usuario: Username who is rejecting
        razon: Reason for rejection

    Returns:
        True if rejected successfully
    """
    estado_anterior = planilla.estado_aprobacion
    planilla.estado_aprobacion = EstadoAprobacion.BORRADOR
    planilla.aprobado_por = None
    planilla.aprobado_en = None

    # Create audit log
    descripcion = f"Rechazó planilla '{planilla.nombre}'"
    if razon:
        descripcion += f" - Razón: {razon}"

    crear_log_auditoria_planilla(
        planilla=planilla,
        accion="rejected",
        usuario=usuario,
        descripcion=descripcion,
        estado_anterior=estado_anterior,
        estado_nuevo=EstadoAprobacion.BORRADOR,
    )

    return True


def marcar_planilla_como_borrador_si_editada(
    planilla: Planilla,
    usuario: str,
    cambios: Dict[str, Any],
) -> None:
    """Mark planilla as draft if it was edited while approved.

    When an approved planilla is edited, it must return to draft status
    unless it was created by a plugin.

    Args:
        planilla: The planilla that was edited
        usuario: Username who edited
        cambios: Dictionary of changes made
    """
    # Don't change status if created by plugin
    if planilla.creado_por_plugin:
        return

    # If currently approved, mark as draft
    if planilla.estado_aprobacion == EstadoAprobacion.APROBADO:
        estado_anterior = planilla.estado_aprobacion
        planilla.estado_aprobacion = EstadoAprobacion.BORRADOR
        planilla.aprobado_por = None
        planilla.aprobado_en = None

        # Create audit log
        descripcion_cambios = generar_descripcion_cambios(cambios)

        crear_log_auditoria_planilla(
            planilla=planilla,
            accion="updated",
            usuario=usuario,
            descripcion=f"Editó planilla '{planilla.nombre}' - {descripcion_cambios}. Estado cambiado a borrador.",
            cambios=cambios,
            estado_anterior=estado_anterior,
            estado_nuevo=EstadoAprobacion.BORRADOR,
        )


# ============================================================================
# NOMINA AUDIT FUNCTIONS
# ============================================================================


def crear_log_auditoria_nomina(
    nomina: Nomina,
    accion: str,
    usuario: str,
    descripcion: Optional[str] = None,
    cambios: Optional[Dict[str, Any]] = None,
    estado_anterior: Optional[str] = None,
    estado_nuevo: Optional[str] = None,
) -> NominaAuditLog:
    """Create an audit log entry for a nomina state change.

    Args:
        nomina: The nomina that changed state
        accion: Action performed (generated, approved, applied, cancelled, etc.)
        usuario: Username who performed the action
        descripcion: Human-readable description of the change
        cambios: Dictionary of field-level changes
        estado_anterior: Previous state
        estado_nuevo: New state

    Returns:
        The created audit log entry
    """
    log = NominaAuditLog(
        nomina_id=nomina.id,
        accion=accion,
        usuario=usuario,
        descripcion=descripcion,
        cambios=cambios or {},
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
    )

    db.session.add(log)
    return log


def aprobar_nomina(nomina: Nomina, usuario: str) -> bool:
    """Approve a nomina.

    Changes state from 'generated' to 'approved' and records approval information.

    Args:
        nomina: The nomina to approve
        usuario: Username who is approving

    Returns:
        True if approved successfully, False if already approved or invalid state
    """
    if nomina.estado != NominaEstado.GENERADO:
        return False

    estado_anterior = nomina.estado
    nomina.estado = NominaEstado.APROBADO
    nomina.aprobado_por = usuario
    nomina.aprobado_en = utc_now()

    # Create audit log
    crear_log_auditoria_nomina(
        nomina=nomina,
        accion="approved",
        usuario=usuario,
        descripcion=f"Aprobó nómina del período {nomina.periodo_inicio} al {nomina.periodo_fin}",
        estado_anterior=estado_anterior,
        estado_nuevo=NominaEstado.APROBADO,
    )

    return True


def aplicar_nomina(nomina: Nomina, usuario: str) -> bool:
    """Apply a nomina (mark as paid/executed).

    Changes state from 'approved' to 'applied' and records application information.

    Args:
        nomina: The nomina to apply
        usuario: Username who is applying

    Returns:
        True if applied successfully, False if not in approved state
    """
    if nomina.estado != NominaEstado.APROBADO:
        return False

    estado_anterior = nomina.estado
    nomina.estado = NominaEstado.APLICADO
    nomina.aplicado_por = usuario
    nomina.aplicado_en = utc_now()

    # Create audit log
    crear_log_auditoria_nomina(
        nomina=nomina,
        accion="applied",
        usuario=usuario,
        descripcion=f"Aplicó nómina del período {nomina.periodo_inicio} al {nomina.periodo_fin}",
        estado_anterior=estado_anterior,
        estado_nuevo=NominaEstado.APLICADO,
    )

    return True


def anular_nomina(nomina: Nomina, usuario: str, razon: str) -> bool:
    """Cancel/void a nomina.

    Changes state to 'cancelled' and records cancellation information.

    Args:
        nomina: The nomina to cancel
        usuario: Username who is cancelling
        razon: Reason for cancellation

    Returns:
        True if cancelled successfully, False if already cancelled
    """
    if nomina.estado == NominaEstado.ANULADO:
        return False

    estado_anterior = nomina.estado
    nomina.estado = NominaEstado.ANULADO
    nomina.anulado_por = usuario
    nomina.anulado_en = utc_now()
    nomina.razon_anulacion = razon

    # Create audit log
    crear_log_auditoria_nomina(
        nomina=nomina,
        accion="cancelled",
        usuario=usuario,
        descripcion=f"Anuló nómina del período {nomina.periodo_inicio} al {nomina.periodo_fin} - Razón: {razon}",
        estado_anterior=estado_anterior,
        estado_nuevo=NominaEstado.ANULADO,
    )

    return True


# ============================================================================
# REGLA CALCULO AUDIT FUNCTIONS
# ============================================================================


def crear_log_auditoria_regla_calculo(
    regla_calculo: ReglaCalculo,
    accion: str,
    usuario: str,
    descripcion: Optional[str] = None,
    cambios: Optional[Dict[str, Any]] = None,
    estado_anterior: Optional[str] = None,
    estado_nuevo: Optional[str] = None,
) -> ReglaCalculoAuditLog:
    """Create an audit log entry for a calculation rule change.

    Args:
        regla_calculo: The calculation rule that was changed
        accion: Action performed (created, updated, approved, rejected, etc.)
        usuario: Username who performed the action
        descripcion: Human-readable description of the change
        cambios: Dictionary of field-level changes
        estado_anterior: Previous approval status
        estado_nuevo: New approval status

    Returns:
        The created audit log entry
    """
    log = ReglaCalculoAuditLog(
        regla_calculo_id=regla_calculo.id,
        accion=accion,
        usuario=usuario,
        descripcion=descripcion,
        cambios=cambios or {},
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
    )

    db.session.add(log)
    return log


def aprobar_regla_calculo(regla_calculo: ReglaCalculo, usuario: str) -> bool:
    """Approve a calculation rule.

    Changes status from 'draft' to 'approved' and records approval information.

    Args:
        regla_calculo: The calculation rule to approve
        usuario: Username who is approving

    Returns:
        True if approved successfully, False if already approved or invalid
    """
    if regla_calculo.estado_aprobacion == EstadoAprobacion.APROBADO:
        return False

    estado_anterior = regla_calculo.estado_aprobacion
    regla_calculo.estado_aprobacion = EstadoAprobacion.APROBADO
    regla_calculo.aprobado_por = usuario
    regla_calculo.aprobado_en = utc_now()

    # Create audit log
    crear_log_auditoria_regla_calculo(
        regla_calculo=regla_calculo,
        accion="approved",
        usuario=usuario,
        descripcion=(
            "Aprobó regla de cálculo "
            + f"'{regla_calculo.nombre}' (código: {regla_calculo.codigo}, "
            + f"versión: {regla_calculo.version})"
        ),
        estado_anterior=estado_anterior,
        estado_nuevo=EstadoAprobacion.APROBADO,
    )

    return True


def rechazar_regla_calculo(
    regla_calculo: ReglaCalculo,
    usuario: str,
    razon: Optional[str] = None,
) -> bool:
    """Reject a calculation rule (keep as draft).

    Args:
        regla_calculo: The calculation rule to reject
        usuario: Username who is rejecting
        razon: Reason for rejection

    Returns:
        True if rejected successfully
    """
    estado_anterior = regla_calculo.estado_aprobacion
    regla_calculo.estado_aprobacion = EstadoAprobacion.BORRADOR
    regla_calculo.aprobado_por = None
    regla_calculo.aprobado_en = None

    # Create audit log
    descripcion = (
        f"Rechazó regla de cálculo '{regla_calculo.nombre}' "
        + f"(código: {regla_calculo.codigo}, versión: {regla_calculo.version})"
    )
    if razon:
        descripcion += f" - Razón: {razon}"

    crear_log_auditoria_regla_calculo(
        regla_calculo=regla_calculo,
        accion="rejected",
        usuario=usuario,
        descripcion=descripcion,
        estado_anterior=estado_anterior,
        estado_nuevo=EstadoAprobacion.BORRADOR,
    )

    return True


def marcar_regla_calculo_como_borrador_si_editada(
    regla_calculo: ReglaCalculo,
    usuario: str,
    cambios: Dict[str, Any],
) -> None:
    """Mark calculation rule as draft if it was edited while approved.

    When an approved calculation rule is edited, it must return to draft status
    unless it was created by a plugin.

    Args:
        regla_calculo: The calculation rule that was edited
        usuario: Username who edited
        cambios: Dictionary of changes made
    """
    # Don't change status if created by plugin
    if regla_calculo.creado_por_plugin:
        return

    # If currently approved, mark as draft
    if regla_calculo.estado_aprobacion == EstadoAprobacion.APROBADO:
        estado_anterior = regla_calculo.estado_aprobacion
        regla_calculo.estado_aprobacion = EstadoAprobacion.BORRADOR
        regla_calculo.aprobado_por = None
        regla_calculo.aprobado_en = None

        # Create audit log
        descripcion_cambios = generar_descripcion_cambios(cambios)

        crear_log_auditoria_regla_calculo(
            regla_calculo=regla_calculo,
            accion="updated",
            usuario=usuario,
            descripcion=(
                f"Editó regla de cálculo '{regla_calculo.nombre}' - "
                + f"{descripcion_cambios}. Estado cambiado a borrador."
            ),
            cambios=cambios,
            estado_anterior=estado_anterior,
            estado_nuevo=EstadoAprobacion.BORRADOR,
        )


def obtener_reglas_calculo_en_borrador(planilla_id: str) -> list:
    """Get all draft calculation rules associated with a planilla.

    Args:
        planilla_id: ID of the planilla

    Returns:
        List of draft calculation rules
    """
    from coati_payroll.model import PlanillaReglaCalculo

    reglas_borrador = (
        db.session.query(ReglaCalculo)
        .join(PlanillaReglaCalculo)
        .filter(
            PlanillaReglaCalculo.planilla_id == planilla_id,
            ReglaCalculo.estado_aprobacion == EstadoAprobacion.BORRADOR,
            ReglaCalculo.activo.is_(true()),
        )
        .all()
    )

    return reglas_borrador


def validar_configuracion_nomina(planilla_id: str) -> Dict[str, Any]:
    """Validate payroll configuration before execution.

    Checks for draft concepts and calculation rules that may affect payroll accuracy.
    Returns warnings but does not prevent execution (allows test runs).

    Args:
        planilla_id: ID of the planilla

    Returns:
        Dictionary with validation results:
        {
            "tiene_advertencias": bool,
            "advertencias": list of warning messages,
            "conceptos_borrador": dict with draft concepts,
            "reglas_borrador": list of draft calculation rules
        }
    """
    advertencias = []

    # Check for draft concepts
    conceptos_borrador = obtener_conceptos_en_borrador(planilla_id)

    if conceptos_borrador["percepciones"]:
        percepciones_nombres = [p.nombre for p in conceptos_borrador["percepciones"]]
        advertencias.append(
            f"⚠️ Hay {len(percepciones_nombres)} percepción(es) en estado BORRADOR: {', '.join(percepciones_nombres)}"
        )

    if conceptos_borrador["deducciones"]:
        deducciones_nombres = [d.nombre for d in conceptos_borrador["deducciones"]]
        advertencias.append(
            f"⚠️ Hay {len(deducciones_nombres)} deducción(es) en estado BORRADOR: {', '.join(deducciones_nombres)}"
        )

    if conceptos_borrador["prestaciones"]:
        prestaciones_nombres = [p.nombre for p in conceptos_borrador["prestaciones"]]
        advertencias.append(
            f"⚠️ Hay {len(prestaciones_nombres)} prestación(es) en estado BORRADOR: {', '.join(prestaciones_nombres)}"
        )

    # Check for draft calculation rules
    reglas_borrador = obtener_reglas_calculo_en_borrador(planilla_id)

    if reglas_borrador:
        reglas_nombres = [f"{r.nombre} (v{r.version})" for r in reglas_borrador]
        advertencias.append(
            f"⚠️ Hay {len(reglas_nombres)} regla(s) de cálculo en estado BORRADOR: {', '.join(reglas_nombres)}"
        )

    return {
        "tiene_advertencias": bool(advertencias),
        "advertencias": advertencias,
        "conceptos_borrador": conceptos_borrador,
        "reglas_borrador": reglas_borrador,
    }
