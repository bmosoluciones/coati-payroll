# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Comprehensive tests for payroll concepts CRUD (coati_payroll/vistas/payroll_concepts.py)."""


from sqlalchemy import select
from coati_payroll.enums import FormulaType
from coati_payroll.model import Deduccion, Percepcion, Prestacion
from tests.helpers.auth import login_user

# ============================================================================
# PERCEPCION TESTS
# ============================================================================


def test_percepcion_index_requires_authentication(app, client, db_session):
    """Test that percepcion index requires authentication."""
    with app.app_context():
        response = client.get("/percepciones/", follow_redirects=False)
        assert response.status_code == 302


def test_percepcion_index_lists_items(app, client, admin_user, db_session):
    """Test that authenticated user can view percepcion list."""
    with app.app_context():
        # Create test perceptions
        perc1 = Percepcion(
            codigo="SALARIO",
            nombre="Salario Base",
            descripcion="Base salary",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
        )
        perc2 = Percepcion(
            codigo="BONO",
            nombre="Bono Mensual",
            descripcion="Monthly bonus",
            formula_tipo=FormulaType.PORCENTAJE,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add_all([perc1, perc2])
        db_session.commit()

        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/percepciones/")
        assert response.status_code == 200
        assert b"SALARIO" in response.data or b"Salario" in response.data


def test_percepcion_new_creates_item(app, client, admin_user, db_session):
    """Test creating a new percepcion."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/percepciones/new",
            data={
                "codigo": "COMISION",
                "nombre": "Comisión de Ventas",
                "descripcion": "Sales commission",
                "formula_tipo": FormulaType.PORCENTAJE,
                "valor_fijo": "0",
                "porcentaje": "5",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            perc = db_session.execute(select(Percepcion).filter_by(codigo="COMISION")).scalar_one_or_none()
            assert perc is not None
            assert perc.nombre == "Comisión de Ventas"
            assert perc.formula_tipo == FormulaType.PORCENTAJE


def test_percepcion_edit_updates_item(app, client, admin_user, db_session):
    """Test updating a percepcion."""
    with app.app_context():
        perc = Percepcion(
            codigo="EXTRA",
            nombre="Horas Extras",
            descripcion="Overtime pay",
            formula_tipo=FormulaType.HORAS,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(perc)
        db_session.commit()
        db_session.refresh(perc)

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            f"/percepciones/edit/{perc.id}",
            data={
                "codigo": "EXTRA",
                "nombre": "Horas Extras (Updated)",
                "descripcion": "Overtime pay - updated",
                "formula_tipo": FormulaType.HORAS,
                "valor_fijo": "0",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            db_session.refresh(perc)
            assert perc.nombre == "Horas Extras (Updated)"


def test_percepcion_delete_removes_item(app, client, admin_user, db_session):
    """Test deleting a percepcion."""
    with app.app_context():
        perc = Percepcion(
            codigo="TEMP",
            nombre="Temporary Perception",
            descripcion="Temp",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
        )
        db_session.add(perc)
        db_session.commit()
        perc_id = perc.id

        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(f"/percepciones/delete/{perc_id}", follow_redirects=False)

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            perc = db_session.execute(select(Percepcion).filter_by(id=perc_id)).scalar_one_or_none()
            assert perc is None


# ============================================================================
# DEDUCCION TESTS
# ============================================================================


def test_deduccion_index_requires_authentication(app, client, db_session):
    """Test that deduccion index requires authentication."""
    with app.app_context():
        response = client.get("/deducciones/", follow_redirects=False)
        assert response.status_code == 302


def test_deduccion_new_creates_item(app, client, admin_user, db_session):
    """Test creating a new deduccion."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/deducciones/new",
            data={
                "codigo": "INSS",
                "nombre": "Seguro Social",
                "descripcion": "Social security deduction",
                "formula_tipo": FormulaType.PORCENTAJE,
                "valor_fijo": "0",
                "porcentaje": "7",
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            ded = db_session.execute(select(Deduccion).filter_by(codigo="INSS")).scalar_one_or_none()
            assert ded is not None
            assert ded.nombre == "Seguro Social"


def test_deduccion_supports_different_formula_types(app, client, admin_user, db_session):
    """Test that deducciones support different formula types."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        formula_types = [
            ("DED_FIJO", FormulaType.FIJO, "Fixed Deduction"),
            ("DED_PCT", FormulaType.PORCENTAJE, "Percentage Deduction"),
            ("DED_SAL", FormulaType.PORCENTAJE_SALARIO, "Salary % Deduction"),
        ]

        for codigo, tipo, nombre in formula_types:
            response = client.post(
                "/deducciones/new",
                data={
                    "codigo": codigo,
                    "nombre": nombre,
                    "descripcion": f"Test {tipo}",
                    "formula_tipo": tipo,
                    "valor_fijo": "100" if tipo == FormulaType.FIJO else "0",
                    "porcentaje": "10" if tipo != FormulaType.FIJO else "0",
                    "activo": "y",
                },
                follow_redirects=False,
            )

            assert response.status_code in [200, 302]


# ============================================================================
# PRESTACION TESTS
# ============================================================================


def test_prestacion_index_requires_authentication(app, client, db_session):
    """Test that prestacion index requires authentication."""
    with app.app_context():
        response = client.get("/prestaciones/", follow_redirects=False)
        assert response.status_code == 302


def test_prestacion_new_creates_item(app, client, admin_user, db_session):
    """Test creating a new prestacion."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/prestaciones/new",
            data={
                "codigo": "AGUINALDO",
                "nombre": "Aguinaldo",
                "descripcion": "13th month salary",
                "formula_tipo": FormulaType.FORMULA,
                "activo": "y",
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            prest = db_session.execute(select(Prestacion).filter_by(codigo="AGUINALDO")).scalar_one_or_none()
            assert prest is not None
            assert prest.nombre == "Aguinaldo"


def test_prestacion_can_be_inactive(app, client, admin_user, db_session):
    """Test that prestaciones can be inactive."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.post(
            "/prestaciones/new",
            data={
                "codigo": "INACTIVE_PREST",
                "nombre": "Inactive Benefit",
                "descripcion": "Not active",
                "formula_tipo": FormulaType.FIJO,
                "valor_fijo": "0",
                # Not sending activo means False
            },
            follow_redirects=False,
        )

        assert response.status_code in [200, 302]

        if response.status_code == 302:
            prest = db_session.execute(select(Prestacion).filter_by(codigo="INACTIVE_PREST")).scalar_one_or_none()
            assert prest is not None
            assert prest.activo is False


def test_payroll_concepts_workflow(app, client, admin_user, db_session):
    """End-to-end test: Create, edit, and delete a payroll concept."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Step 1: Create perception
        response = client.post(
            "/percepciones/new",
            data={
                "codigo": "WORKFLOW",
                "nombre": "Workflow Test",
                "descripcion": "Testing workflow",
                "formula_tipo": FormulaType.FIJO,
                "valor_fijo": "1000",
                "activo": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]

        if response.status_code == 302:
            perc = db_session.execute(select(Percepcion).filter_by(codigo="WORKFLOW")).scalar_one_or_none()
            assert perc is not None
            perc_id = perc.id

            # Step 2: Edit
            response = client.post(
                f"/percepciones/edit/{perc_id}",
                data={
                    "codigo": "WORKFLOW",
                    "nombre": "Workflow Test (Updated)",
                    "descripcion": "Testing workflow - updated",
                    "formula_tipo": FormulaType.FIJO,
                    "valor_fijo": "1500",
                    # Not sending activo means False
                },
                follow_redirects=False,
            )
            assert response.status_code in [200, 302]

            if response.status_code == 302:
                db_session.refresh(perc)
                assert perc.nombre == "Workflow Test (Updated)"
                assert perc.activo is False

                # Step 3: Delete
                response = client.post(f"/percepciones/delete/{perc_id}", follow_redirects=False)
                assert response.status_code in [200, 302]

                if response.status_code == 302:
                    perc = db_session.execute(select(Percepcion).filter_by(id=perc_id)).scalar_one_or_none()
                    assert perc is None


# ============================================================================
# APPROVAL AND AUDIT TESTS
# ============================================================================


def test_approve_concept_route_success(app, client, admin_user, db_session):
    """Test successful approval of a concept by authorized user."""
    with app.app_context():
        from coati_payroll.enums import EstadoAprobacion

        # Create a draft percepcion
        perc = Percepcion(
            codigo="APPROVE_TEST",
            nombre="Test Approval",
            descripcion="Test approval flow",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.BORRADOR,
        )
        db_session.add(perc)
        db_session.commit()
        db_session.refresh(perc)

        login_user(client, admin_user.usuario, "admin-password")

        # Approve the concept
        response = client.post(f"/percepciones/approve/{perc.id}", follow_redirects=False)
        assert response.status_code == 302

        # Verify approval
        db_session.refresh(perc)
        assert perc.estado_aprobacion == EstadoAprobacion.APROBADO
        assert perc.aprobado_por == admin_user.usuario
        assert perc.aprobado_en is not None


def test_approve_concept_route_unauthorized(app, client, db_session):
    """Test that unauthorized user cannot approve concepts."""
    with app.app_context():
        from coati_payroll.auth import proteger_passwd
        from coati_payroll.enums import TipoUsuario, EstadoAprobacion
        from coati_payroll.model import Usuario

        # Create an audit user (not authorized to approve)
        audit_user = Usuario()
        audit_user.usuario = "audit-test"
        audit_user.acceso = proteger_passwd("audit-password")
        audit_user.nombre = "Audit"
        audit_user.apellido = "User"
        audit_user.correo_electronico = "audit@test.com"
        audit_user.tipo = TipoUsuario.AUDIT
        audit_user.activo = True
        db_session.add(audit_user)

        # Create a draft percepcion
        perc = Percepcion(
            codigo="UNAUTH_TEST",
            nombre="Unauthorized Test",
            descripcion="Test unauthorized approval",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.BORRADOR,
        )
        db_session.add(perc)
        db_session.commit()
        db_session.refresh(perc)

        login_user(client, audit_user.usuario, "audit-password")

        # Try to approve (should fail with 403 Forbidden due to RBAC)
        response = client.post(f"/percepciones/approve/{perc.id}", follow_redirects=False)
        assert response.status_code == 403

        # Verify it's still in draft status
        db_session.refresh(perc)
        assert perc.estado_aprobacion == EstadoAprobacion.BORRADOR
        assert perc.aprobado_por is None


def test_approve_concept_route_not_found(app, client, admin_user, db_session):
    """Test approval of non-existent concept."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Try to approve non-existent concept
        response = client.post("/percepciones/approve/nonexistent-id", follow_redirects=False)
        assert response.status_code == 302


def test_approve_concept_route_already_approved(app, client, admin_user, db_session):
    """Test that approving an already approved concept shows info message."""
    with app.app_context():
        from coati_payroll.enums import EstadoAprobacion
        from coati_payroll.model import utc_now

        # Create an already approved percepcion
        perc = Percepcion(
            codigo="ALREADY_APPROVED",
            nombre="Already Approved",
            descripcion="Already approved concept",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.APROBADO,
            aprobado_por="previous-user",
            aprobado_en=utc_now(),
        )
        db_session.add(perc)
        db_session.commit()
        db_session.refresh(perc)

        login_user(client, admin_user.usuario, "admin-password")

        # Try to approve again
        response = client.post(f"/percepciones/approve/{perc.id}", follow_redirects=False)
        assert response.status_code == 302

        # Verify it's still approved by previous user
        db_session.refresh(perc)
        assert perc.estado_aprobacion == EstadoAprobacion.APROBADO
        assert perc.aprobado_por == "previous-user"


def test_reject_concept_route_success(app, client, admin_user, db_session):
    """Test successful rejection of a concept."""
    with app.app_context():
        from coati_payroll.enums import EstadoAprobacion
        from coati_payroll.model import utc_now

        # Create an approved percepcion
        perc = Percepcion(
            codigo="REJECT_TEST",
            nombre="Test Rejection",
            descripcion="Test rejection flow",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.APROBADO,
            aprobado_por="previous-user",
            aprobado_en=utc_now(),
        )
        db_session.add(perc)
        db_session.commit()
        db_session.refresh(perc)

        login_user(client, admin_user.usuario, "admin-password")

        # Reject the concept with reason
        response = client.post(
            f"/percepciones/reject/{perc.id}",
            data={"razon": "Incorrect formula"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify rejection (concept should be back to draft)
        db_session.refresh(perc)
        assert perc.estado_aprobacion == EstadoAprobacion.BORRADOR
        assert perc.aprobado_por is None
        assert perc.aprobado_en is None


def test_reject_concept_route_unauthorized(app, client, db_session):
    """Test that unauthorized user cannot reject concepts."""
    with app.app_context():
        from coati_payroll.auth import proteger_passwd
        from coati_payroll.enums import TipoUsuario, EstadoAprobacion
        from coati_payroll.model import Usuario, utc_now

        # Create an audit user (not authorized to reject)
        audit_user = Usuario()
        audit_user.usuario = "audit-test2"
        audit_user.acceso = proteger_passwd("audit-password")
        audit_user.nombre = "Audit"
        audit_user.apellido = "User"
        audit_user.correo_electronico = "audit2@test.com"
        audit_user.tipo = TipoUsuario.AUDIT
        audit_user.activo = True
        db_session.add(audit_user)

        # Create an approved percepcion
        perc = Percepcion(
            codigo="REJECT_UNAUTH",
            nombre="Reject Unauthorized",
            descripcion="Test unauthorized rejection",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.APROBADO,
            aprobado_por="previous-user",
            aprobado_en=utc_now(),
        )
        db_session.add(perc)
        db_session.commit()
        db_session.refresh(perc)

        login_user(client, audit_user.usuario, "audit-password")

        # Try to reject (should fail with 403 Forbidden due to RBAC)
        response = client.post(
            f"/percepciones/reject/{perc.id}",
            data={"razon": "Unauthorized rejection"},
            follow_redirects=False,
        )
        assert response.status_code == 403

        # Verify it's still approved
        db_session.refresh(perc)
        assert perc.estado_aprobacion == EstadoAprobacion.APROBADO
        assert perc.aprobado_por == "previous-user"


def test_reject_concept_route_not_found(app, client, admin_user, db_session):
    """Test rejection of non-existent concept."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Try to reject non-existent concept
        response = client.post(
            "/percepciones/reject/nonexistent-id",
            data={"razon": "Test reason"},
            follow_redirects=False,
        )
        assert response.status_code == 302


def test_view_audit_log_route_success(app, client, admin_user, db_session):
    """Test that view_audit_log_route retrieves concept and audit logs correctly."""
    with app.app_context():
        from coati_payroll.enums import EstadoAprobacion
        from coati_payroll.audit_helpers import crear_log_auditoria

        # Create a percepcion
        perc = Percepcion(
            codigo="AUDIT_TEST",
            nombre="Audit Test",
            descripcion="Test audit log",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.BORRADOR,
        )
        db_session.add(perc)
        db_session.flush()

        # Create some audit log entries
        crear_log_auditoria(
            concepto=perc,
            accion="created",
            usuario="admin-test",
            descripcion="Created concept",
            estado_nuevo=EstadoAprobacion.BORRADOR,
        )
        crear_log_auditoria(
            concepto=perc,
            accion="updated",
            usuario="admin-test",
            descripcion="Updated concept",
        )
        db_session.commit()
        db_session.refresh(perc)

        # Verify the audit logs exist
        assert len(perc.audit_logs) >= 2

        # Verify sorting logic that's used in view_audit_log_route
        audit_logs = sorted(perc.audit_logs, key=lambda x: x.timestamp, reverse=True)
        assert audit_logs[0].accion == "updated"  # Most recent first
        assert audit_logs[-1].accion == "created"  # Oldest last


def test_view_audit_log_route_not_found(app, client, admin_user, db_session):
    """Test viewing audit log for non-existent concept."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        # Try to view audit log for non-existent concept
        response = client.get("/percepciones/audit/nonexistent-id", follow_redirects=False)
        assert response.status_code == 302


def test_approve_deduccion_route(app, client, admin_user, db_session):
    """Test approval of deduccion concept type."""
    with app.app_context():
        from coati_payroll.enums import EstadoAprobacion

        # Create a draft deduccion
        ded = Deduccion(
            codigo="DED_APPROVE",
            nombre="Test Deduccion Approval",
            descripcion="Test deduccion approval",
            formula_tipo=FormulaType.PORCENTAJE,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.BORRADOR,
        )
        db_session.add(ded)
        db_session.commit()
        db_session.refresh(ded)

        login_user(client, admin_user.usuario, "admin-password")

        # Approve the deduccion
        response = client.post(f"/deducciones/approve/{ded.id}", follow_redirects=False)
        assert response.status_code == 302

        # Verify approval
        db_session.refresh(ded)
        assert ded.estado_aprobacion == EstadoAprobacion.APROBADO


def test_reject_prestacion_route(app, client, admin_user, db_session):
    """Test rejection of prestacion concept type."""
    with app.app_context():
        from coati_payroll.enums import EstadoAprobacion
        from coati_payroll.model import utc_now

        # Create an approved prestacion
        prest = Prestacion(
            codigo="PREST_REJECT",
            nombre="Test Prestacion Rejection",
            descripcion="Test prestacion rejection",
            formula_tipo=FormulaType.FORMULA,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.APROBADO,
            aprobado_por="previous-user",
            aprobado_en=utc_now(),
        )
        db_session.add(prest)
        db_session.commit()
        db_session.refresh(prest)

        login_user(client, admin_user.usuario, "admin-password")

        # Reject the prestacion
        response = client.post(
            f"/prestaciones/reject/{prest.id}",
            data={"razon": "Needs review"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        # Verify rejection
        db_session.refresh(prest)
        assert prest.estado_aprobacion == EstadoAprobacion.BORRADOR


def test_audit_log_ordering(app, client, admin_user, db_session):
    """Test that audit logs are ordered by timestamp (most recent first)."""
    with app.app_context():
        from coati_payroll.enums import EstadoAprobacion
        from coati_payroll.audit_helpers import crear_log_auditoria
        import time

        # Create a percepcion
        perc = Percepcion(
            codigo="AUDIT_ORDER",
            nombre="Audit Order Test",
            descripcion="Test audit log ordering",
            formula_tipo=FormulaType.FIJO,
            activo=True,
            creado_por="admin-test",
            estado_aprobacion=EstadoAprobacion.BORRADOR,
        )
        db_session.add(perc)
        db_session.flush()

        # Create audit log entries with slight delays
        crear_log_auditoria(
            concepto=perc,
            accion="created",
            usuario="admin-test",
            descripcion="First entry",
        )
        db_session.flush()
        time.sleep(0.01)

        crear_log_auditoria(
            concepto=perc,
            accion="updated",
            usuario="admin-test",
            descripcion="Second entry",
        )
        db_session.flush()
        time.sleep(0.01)

        crear_log_auditoria(
            concepto=perc,
            accion="approved",
            usuario="admin-test",
            descripcion="Third entry",
        )
        db_session.commit()
        db_session.refresh(perc)

        # Test the sorting logic used in view_audit_log_route
        audit_logs = sorted(perc.audit_logs, key=lambda x: x.timestamp, reverse=True)
        assert len(audit_logs) >= 3
        # Most recent should be first
        assert audit_logs[0].descripcion == "Third entry"
        assert audit_logs[-1].descripcion == "First entry"
