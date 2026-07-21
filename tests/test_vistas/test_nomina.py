# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for top-level nominas view (/nominas/)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from coati_payroll.model import Nomina
from tests.helpers.auth import login_user


@pytest.fixture
def tipo_planilla(app, db_session):
    """Create a TipoPlanilla for testing."""
    with app.app_context():
        from coati_payroll.model import TipoPlanilla

        tipo = TipoPlanilla(
            codigo="MENSUAL-NOMINAS",
            descripcion="Planilla Mensual",
            periodicidad="monthly",
            dias=30,
            periodos_por_anio=12,
            mes_inicio_fiscal=1,
            dia_inicio_fiscal=1,
            activo=True,
        )
        db_session.add(tipo)
        db_session.commit()
        db_session.refresh(tipo)
        return tipo


@pytest.fixture
def moneda(app, db_session):
    """Create a Moneda for testing."""
    with app.app_context():
        from coati_payroll.model import Moneda

        moneda = Moneda(codigo="NIO", nombre="Cordoba", simbolo="C$", activo=True)
        db_session.add(moneda)
        db_session.commit()
        db_session.refresh(moneda)
        return moneda


@pytest.fixture
def empresa(app, db_session):
    """Create an Empresa for testing."""
    with app.app_context():
        from coati_payroll.model import Empresa

        empresa = Empresa(
            codigo="EMP-NOM",
            razon_social="Empresa Nominas, S.A.",
            ruc="1234567890",
            activo=True,
        )
        db_session.add(empresa)
        db_session.commit()
        db_session.refresh(empresa)
        return empresa


@pytest.fixture
def planilla(app, db_session, tipo_planilla, moneda, empresa, admin_user):
    """Create a Planilla for testing."""
    with app.app_context():
        from coati_payroll.model import Planilla

        planilla = Planilla(
            nombre="Planilla Nominas Global",
            tipo_planilla_id=tipo_planilla.id,
            moneda_id=moneda.id,
            empresa_id=empresa.id,
            periodo_fiscal_inicio=date(2025, 1, 1),
            periodo_fiscal_fin=date(2025, 12, 31),
            activo=True,
            creado_por=admin_user.usuario,
        )
        db_session.add(planilla)
        db_session.commit()
        db_session.refresh(planilla)
        return planilla


@pytest.fixture
def nomina(app, db_session, planilla, admin_user):
    """Create a Nomina for testing."""
    with app.app_context():
        nomina = Nomina(
            planilla_id=planilla.id,
            periodo_inicio=date(2025, 2, 1),
            periodo_fin=date(2025, 2, 15),
            generado_por=admin_user.usuario,
            estado="generated",
            total_bruto=Decimal("1000.00"),
            total_deducciones=Decimal("100.00"),
            total_neto=Decimal("900.00"),
        )
        db_session.add(nomina)
        db_session.commit()
        db_session.refresh(nomina)
        return nomina


def test_nomina_index_requires_authentication(app, client, db_session):
    """GET /nominas/ should require authentication."""
    with app.app_context():
        response = client.get("/nominas/", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.location


def test_nomina_index_shows_planilla_link_and_id(app, client, admin_user, db_session, planilla, nomina):
    """Authenticated user should see planilla name as link and muted planilla ID."""
    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        response = client.get("/nominas/")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        assert f"/planilla/{planilla.id}/edit" in html
        assert f"ID: {planilla.id}" in html
        assert planilla.nombre in html


def test_nomina_index_renders_fallback_when_nomina_has_no_planilla(app, client, admin_user, db_session):
    """Template should render '-' safely if a nomina item has no planilla relationship."""

    class _FakePagination:
        def __init__(self, items):
            self.items = items
            self.pages = 1
            self.page = 1
            self.per_page = 20
            self.total = len(items)
            self.has_prev = False
            self.prev_num = None
            self.has_next = False
            self.next_num = None

        def iter_pages(self, **_kwargs):
            return [1]

    class _FakeExecuteResult:
        def scalars(self):
            return self

        def all(self):
            return []

    fake_nomina = SimpleNamespace(
        id="01FAKENOMINA00000000000000",
        planilla=None,
        planilla_id=None,
        periodo_inicio=date(2025, 1, 1),
        periodo_fin=date(2025, 1, 15),
        fecha_generacion=date(2025, 1, 15),
        estado="generated",
        total_empleados=0,
        empleados_procesados=0,
        total_bruto=Decimal("0.00"),
        total_deducciones=Decimal("0.00"),
        total_neto=Decimal("0.00"),
        generado_por="tester",
    )

    with app.app_context():
        login_user(client, admin_user.usuario, "admin-password")

        with patch("coati_payroll.vistas.nomina.db.paginate", return_value=_FakePagination([fake_nomina])):
            with patch("coati_payroll.vistas.nomina.db.session.execute", return_value=_FakeExecuteResult()):
                response = client.get("/nominas/")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "<strong>-</strong>" in html
