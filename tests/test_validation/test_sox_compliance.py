# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""SOX Compliance and Data Traceability Validation Tests.

This test suite validates that the audit logs, approval workflows, draft status reset
mechanisms, and consistent recalculation features function properly to meet
SOX compliance (e.g., separation of duties, traceability, and reproducibility).
"""

from __future__ import annotations

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from coati_payroll.enums import EstadoAprobacion, NominaEstado, TipoUsuario
from coati_payroll.model import (
    Percepcion,
    Deduccion,
    Prestacion,
    Planilla,
    Nomina,
    ReglaCalculo,
    ConceptoAuditLog,
    PlanillaAuditLog,
    NominaAuditLog,
    ReglaCalculoAuditLog,
    TipoPlanilla,
    Empresa,
    Moneda,
    db,
)
from coati_payroll.audit_helpers import (
    puede_aprobar_concepto,
    aprobar_concepto,
    rechazar_concepto,
    marcar_como_borrador_si_editado,
    detectar_cambios,
    aprobar_planilla,
    rechazar_planilla,
    marcar_planilla_como_borrador_si_editada,
    aprobar_nomina,
    aplicar_nomina,
    anular_nomina,
    aprobar_regla_calculo,
    rechazar_regla_calculo,
    marcar_regla_calculo_como_borrador_si_editada,
)
from coati_payroll.vistas.planilla.services.nomina_service import NominaService


@pytest.fixture
def sox_setup(app, db_session):
    """Setup basic SOX objects required by tests."""
    with app.app_context():
        tipo = TipoPlanilla(
            codigo="MENSUAL",
            descripcion="Planilla Mensual",
            periodicidad="monthly",
            activo=True,
        )
        db_session.add(tipo)

        moneda = Moneda(codigo="USD", nombre="Dolar", simbolo="$", activo=True)
        db_session.add(moneda)

        empresa = Empresa(
            codigo="TEST",
            razon_social="Test Company S.A.",
            ruc="123456789",
            activo=True,
        )
        db_session.add(empresa)
        db_session.commit()

        db_session.refresh(tipo)
        db_session.refresh(moneda)
        db_session.refresh(empresa)

        return {
            "tipo_planilla": tipo,
            "moneda": moneda,
            "empresa": empresa,
        }


def test_sox_approval_roles():
    """Verify that only authorized roles (ADMIN/HHRR) can approve concepts."""
    assert puede_aprobar_concepto(TipoUsuario.ADMIN) is True
    assert puede_aprobar_concepto(TipoUsuario.HHRR) is True
    assert puede_aprobar_concepto(TipoUsuario.AUDIT) is False


def test_sox_concept_approval_workflow(app, db_session):
    """Test approval and rejection workflows for payroll concepts."""
    with app.app_context():
        # Create a perception in draft status
        percepcion = Percepcion(
            codigo="PERC_SOX",
            nombre="Bono Especial",
            estado_aprobacion=EstadoAprobacion.BORRADOR,
            activo=True,
        )
        db_session.add(percepcion)
        db_session.commit()

        # Approve perception
        approved = aprobar_concepto(percepcion, usuario="admin_user")
        assert approved is True
        assert percepcion.estado_aprobacion == EstadoAprobacion.APROBADO
        assert percepcion.aprobado_por == "admin_user"
        assert percepcion.aprobado_en is not None

        # Double approval should fail
        assert aprobar_concepto(percepcion, usuario="admin_user") is False

        # Reject/Return to draft
        rejected = rechazar_concepto(percepcion, usuario="hr_user", razon="Faltan justificaciones")
        assert rejected is True
        assert percepcion.estado_aprobacion == EstadoAprobacion.BORRADOR
        assert percepcion.aprobado_por is None
        assert percepcion.aprobado_en is None

        # Verify audit logs exist
        logs = (
            db_session.execute(db.select(ConceptoAuditLog).filter(ConceptoAuditLog.percepcion_id == percepcion.id))
            .scalars()
            .all()
        )
        assert len(logs) >= 2

        # Check approval log
        approval_log = next(log for log in logs if log.accion == "approved")
        assert approval_log.usuario == "admin_user"
        assert "Bono Especial" in approval_log.descripcion

        # Check rejection log
        rejection_log = next(log for log in logs if log.accion == "rejected")
        assert rejection_log.usuario == "hr_user"
        assert "Faltan justificaciones" in rejection_log.descripcion


def test_sox_concept_reverts_to_draft_on_edit(app, db_session):
    """Verify that editing an approved payroll concept reverts its status to Draft."""
    with app.app_context():
        percepcion = Percepcion(
            codigo="PERC_EDIT",
            nombre="Salario Antiguo",
            estado_aprobacion=EstadoAprobacion.APROBADO,
            aprobado_por="prev_admin",
            activo=True,
            monto_default=Decimal("1000.00"),
        )
        db_session.add(percepcion)
        db_session.commit()

        original_data = {
            "nombre": "Salario Antiguo",
            "monto_default": "1000.00",
        }
        new_data = {
            "nombre": "Salario Nuevo",
            "monto_default": "1200.00",
        }

        cambios = detectar_cambios(original_data, new_data)
        assert "nombre" in cambios
        assert "monto_default" in cambios

        percepcion.nombre = "Salario Nuevo"
        percepcion.monto_default = Decimal("1200.00")

        # Mark as draft if edited
        marcar_como_borrador_si_editado(percepcion, usuario="editor_user", cambios=cambios)

        assert percepcion.estado_aprobacion == EstadoAprobacion.BORRADOR
        assert percepcion.aprobado_por is None
        assert percepcion.aprobado_en is None

        # Check audit log entry
        log = db_session.execute(
            db.select(ConceptoAuditLog).filter(
                ConceptoAuditLog.percepcion_id == percepcion.id, ConceptoAuditLog.accion == "updated"
            )
        ).scalar_one()
        assert log.usuario == "editor_user"
        assert "Estado cambiado a borrador" in log.descripcion


def test_sox_planilla_and_rule_draft_on_edit(app, db_session, sox_setup):
    """Verify that editing approved templates or calculation rules resets them to Draft."""
    with app.app_context():
        # 1. Calculation Rule Setup
        regla = ReglaCalculo(
            codigo="RULE_SOX",
            nombre="Regla Original",
            version=1,
            vigente_desde=date(2025, 1, 1),
            estado_aprobacion=EstadoAprobacion.APROBADO,
            aprobado_por="admin",
            activo=True,
        )
        db_session.add(regla)

        # 2. Planilla Setup
        planilla = Planilla(
            nombre="Planilla Original",
            tipo_planilla_id=sox_setup["tipo_planilla"].id,
            moneda_id=sox_setup["moneda"].id,
            empresa_id=sox_setup["empresa"].id,
            estado_aprobacion=EstadoAprobacion.APROBADO,
            aprobado_por="admin",
            activo=True,
        )
        db_session.add(planilla)
        db_session.commit()

        # Edit Rule
        cambios_regla = {"nombre": {"old": "Regla Original", "new": "Regla Modificada"}}
        regla.nombre = "Regla Modificada"
        marcar_regla_calculo_como_borrador_si_editada(regla, usuario="editor", cambios=cambios_regla)
        assert regla.estado_aprobacion == EstadoAprobacion.BORRADOR

        # Edit Planilla
        cambios_planilla = {"nombre": {"old": "Planilla Original", "new": "Planilla Modificada"}}
        planilla.nombre = "Planilla Modificada"
        marcar_planilla_como_borrador_si_editada(planilla, usuario="editor", cambios=cambios_planilla)
        assert planilla.estado_aprobacion == EstadoAprobacion.BORRADOR


def test_sox_nomina_state_transitions_and_audit(app, db_session, sox_setup):
    """Test transitions of Nomina state and corresponding immutable audit logs."""
    with app.app_context():
        planilla = Planilla(
            nombre="SOX Planilla",
            tipo_planilla_id=sox_setup["tipo_planilla"].id,
            moneda_id=sox_setup["moneda"].id,
            empresa_id=sox_setup["empresa"].id,
            activo=True,
        )
        db_session.add(planilla)
        db_session.flush()

        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 1, 1),
            periodo_fin=date(2025, 1, 31),
            estado=NominaEstado.GENERADO,
            total_bruto=Decimal("5000.00"),
            total_deducciones=Decimal("1000.00"),
            total_neto=Decimal("4000.00"),
        )
        db_session.add(nomina)
        db_session.commit()

        # State transition: GENERADO -> APROBADO
        assert aprobar_nomina(nomina, usuario="approver_user") is True
        assert nomina.estado == NominaEstado.APROBADO
        assert nomina.aprobado_por == "approver_user"

        # State transition: APROBADO -> APLICADO
        assert aplicar_nomina(nomina, usuario="finance_user") is True
        assert nomina.estado == NominaEstado.APLICADO
        assert nomina.aplicado_por == "finance_user"

        # State transition: APLICADO -> ANULADO
        assert anular_nomina(nomina, usuario="manager_user", razon="Error de digitación") is True
        assert nomina.estado == NominaEstado.ANULADO
        assert nomina.anulado_por == "manager_user"
        assert nomina.razon_anulacion == "Error de digitación"

        # Verify audit logs for payroll transitions
        logs = (
            db_session.execute(db.select(NominaAuditLog).filter(NominaAuditLog.nomina_id == nomina.id)).scalars().all()
        )
        assert len(logs) == 3

        actions = [log.accion for log in logs]
        assert "approved" in actions
        assert "applied" in actions
        assert "cancelled" in actions


@patch("coati_payroll.vistas.planilla.services.nomina_service.NominaEngine")
def test_sox_recalculation_consistency(mock_engine_class, app, db_session, sox_setup):
    """Test that recalcular_nomina preserves calculation date, stores es_recalculo and audit trail."""
    with app.app_context():
        # Setup Planilla
        planilla = Planilla(
            nombre="Planilla Recalculo",
            tipo_planilla_id=sox_setup["tipo_planilla"].id,
            moneda_id=sox_setup["moneda"].id,
            empresa_id=sox_setup["empresa"].id,
            activo=True,
        )
        db_session.add(planilla)
        db_session.flush()

        # Create original Nomina with original calculation date
        original_fecha_calculo = date(2025, 1, 15)
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 1, 1),
            periodo_fin=date(2025, 1, 31),
            estado=NominaEstado.GENERADO,
            fecha_calculo_original=original_fecha_calculo,
            configuracion_snapshot={
                "empresa_id": sox_setup["empresa"].id,
                "pais_id": "NI",
                "dias_mes_nomina": 30,
                "dias_anio_nomina": 360,
                "horas_jornada_diaria": "8.00",
                "dias_mes_vacaciones": 2.5,
                "dias_anio_vacaciones": 30,
                "considerar_bisiesto_vacaciones": False,
                "dias_anio_financiero": 365,
                "meses_anio_financiero": 12,
                "dias_quincena": 15,
                "liquidacion_modo_dias": "commercial",
                "liquidacion_factor_calendario": False,
                "liquidacion_factor_laboral": False,
                "dias_mes_antiguedad": 30,
                "dias_anio_antiguedad": 360,
                "activo": True,
            },
            tipos_cambio_snapshot={},
            catalogos_snapshot={
                "percepciones": [],
                "deducciones": [],
                "prestaciones": [],
            },
        )
        db_session.add(nomina)
        db_session.commit()

        original_id = nomina.id

        # Mock the engine run to return a new Nomina record with same dates
        mock_engine = MagicMock()
        new_mock_nomina = Nomina(
            id="new_nomina_id_123",
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 1, 1),
            periodo_fin=date(2025, 1, 31),
            estado=NominaEstado.GENERADO,
            fecha_calculo_original=original_fecha_calculo,
        )
        mock_engine.ejecutar.return_value = new_mock_nomina
        mock_engine.errors = []
        mock_engine.warnings = []
        mock_engine_class.return_value = mock_engine

        # Recalculate
        new_nomina, errors, warnings = NominaService.recalcular_nomina(
            nomina=nomina,
            planilla=planilla,
            usuario="sox_auditor",
        )

        assert new_nomina is not None
        assert not errors
        assert new_nomina.es_recalculo is True
        assert new_nomina.nomina_original_id == original_id
        assert new_nomina.fecha_calculo_original == original_fecha_calculo

        # Check audit log for recalculation
        log = db_session.execute(
            db.select(NominaAuditLog).filter(
                NominaAuditLog.nomina_id == new_nomina.id, NominaAuditLog.accion == "recalculated"
            )
        ).scalar_one()
        assert log.usuario == "sox_auditor"
        assert f"Nómina recalculada desde nómina original {original_id}" in log.descripcion
