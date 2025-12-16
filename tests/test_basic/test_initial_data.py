# Copyright 2025 BMO Soluciones, S.A.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for initial_data.py module.

This module tests the functions that load initial data into the database,
including currencies, income concepts, deduction concepts, benefit concepts,
and payroll types.
"""


def test_initial_data_constants_are_defined():
    """
    Test that all initial data constants are defined and not empty.

    Setup:
        - None

    Action:
        - Import constants from initial_data module

    Verification:
        - CURRENCIES list exists and is not empty
        - INCOME_CONCEPTS list exists and is not empty
        - DEDUCTION_CONCEPTS list exists and is not empty
        - BENEFIT_CONCEPTS list exists and is not empty
        - PAYROLL_TYPES list exists and is not empty
    """
    from coati_payroll.initial_data import (
        CURRENCIES,
        INCOME_CONCEPTS,
        DEDUCTION_CONCEPTS,
        BENEFIT_CONCEPTS,
        PAYROLL_TYPES,
    )

    assert CURRENCIES is not None
    assert len(CURRENCIES) > 0
    assert INCOME_CONCEPTS is not None
    assert len(INCOME_CONCEPTS) > 0
    assert DEDUCTION_CONCEPTS is not None
    assert len(DEDUCTION_CONCEPTS) > 0
    assert BENEFIT_CONCEPTS is not None
    assert len(BENEFIT_CONCEPTS) > 0
    assert PAYROLL_TYPES is not None
    assert len(PAYROLL_TYPES) > 0


def test_currencies_have_required_fields():
    """
    Test that all currency entries have required fields.

    Setup:
        - None

    Action:
        - Import CURRENCIES constant

    Verification:
        - Each currency has 'codigo', 'nombre', and 'simbolo' fields
        - All currency codes are valid 3-letter codes
    """
    from coati_payroll.initial_data import CURRENCIES

    for currency in CURRENCIES:
        assert "codigo" in currency
        assert "nombre" in currency
        assert "simbolo" in currency
        assert len(currency["codigo"]) == 3
        assert len(currency["nombre"]) > 0
        assert len(currency["simbolo"]) > 0


def test_income_concepts_have_required_fields():
    """
    Test that all income concept entries have required fields.

    Setup:
        - None

    Action:
        - Import INCOME_CONCEPTS constant

    Verification:
        - Each concept has 'codigo', 'nombre', and 'descripcion' fields
        - All fields are non-empty strings
    """
    from coati_payroll.initial_data import INCOME_CONCEPTS

    for concept in INCOME_CONCEPTS:
        assert "codigo" in concept
        assert "nombre" in concept
        assert "descripcion" in concept
        assert len(concept["codigo"]) > 0
        assert len(concept["nombre"]) > 0
        assert len(concept["descripcion"]) > 0


def test_deduction_concepts_have_required_fields():
    """
    Test that all deduction concept entries have required fields.

    Setup:
        - None

    Action:
        - Import DEDUCTION_CONCEPTS constant

    Verification:
        - Each concept has 'codigo', 'nombre', and 'descripcion' fields
        - All fields are non-empty strings
    """
    from coati_payroll.initial_data import DEDUCTION_CONCEPTS

    for concept in DEDUCTION_CONCEPTS:
        assert "codigo" in concept
        assert "nombre" in concept
        assert "descripcion" in concept
        assert len(concept["codigo"]) > 0
        assert len(concept["nombre"]) > 0
        assert len(concept["descripcion"]) > 0


def test_benefit_concepts_have_required_fields():
    """
    Test that all benefit concept entries have required fields.

    Setup:
        - None

    Action:
        - Import BENEFIT_CONCEPTS constant

    Verification:
        - Each concept has 'codigo', 'nombre', and 'descripcion' fields
        - All fields are non-empty strings
    """
    from coati_payroll.initial_data import BENEFIT_CONCEPTS

    for concept in BENEFIT_CONCEPTS:
        assert "codigo" in concept
        assert "nombre" in concept
        assert "descripcion" in concept
        assert len(concept["codigo"]) > 0
        assert len(concept["nombre"]) > 0
        assert len(concept["descripcion"]) > 0


def test_payroll_types_have_required_fields():
    """
    Test that all payroll type entries have required fields.

    Setup:
        - None

    Action:
        - Import PAYROLL_TYPES constant

    Verification:
        - Each type has required fields
        - Numeric fields have valid values
    """
    from coati_payroll.initial_data import PAYROLL_TYPES

    for payroll_type in PAYROLL_TYPES:
        assert "codigo" in payroll_type
        assert "descripcion" in payroll_type
        assert "dias" in payroll_type
        assert "periodicidad" in payroll_type
        assert "periodos_por_anio" in payroll_type
        assert payroll_type["dias"] > 0
        assert payroll_type["periodos_por_anio"] > 0


def test_load_currencies_creates_currencies(app, db_session):
    """
    Test that load_currencies() creates currency records in the database.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_currencies()

    Verification:
        - Currency records are created in database
        - At least USD currency exists
        - Currency has correct attributes
    """
    from coati_payroll.initial_data import load_currencies
    from coati_payroll.model import Moneda, db

    with app.app_context():
        # Load currencies
        load_currencies()

        # Verify USD currency exists
        usd = db.session.execute(db.select(Moneda).filter_by(codigo="USD")).scalar_one_or_none()

        assert usd is not None
        assert usd.codigo == "USD"
        assert usd.simbolo == "$"
        assert usd.activo is True


def test_load_currencies_is_idempotent(app, db_session):
    """
    Test that load_currencies() can be called multiple times safely.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_currencies() twice

    Verification:
        - No duplicate currencies are created
        - Currency count is correct after both calls
    """
    from coati_payroll.initial_data import load_currencies, CURRENCIES
    from coati_payroll.model import Moneda, db

    with app.app_context():
        # Load currencies first time
        load_currencies()
        first_count = db.session.query(Moneda).count()

        # Load currencies second time
        load_currencies()
        second_count = db.session.query(Moneda).count()

        # Count should be the same
        assert first_count == second_count
        assert first_count == len(CURRENCIES)


def test_load_income_concepts_creates_concepts(app, db_session):
    """
    Test that load_income_concepts() creates income concept records.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_income_concepts()

    Verification:
        - Income concept records are created
        - At least OVERTIME concept exists
        - Concept has correct attributes
    """
    from coati_payroll.initial_data import load_income_concepts
    from coati_payroll.model import Percepcion, db

    with app.app_context():
        # Load income concepts
        load_income_concepts()

        # Verify OVERTIME concept exists
        overtime = db.session.execute(db.select(Percepcion).filter_by(codigo="OVERTIME")).scalar_one_or_none()

        assert overtime is not None
        assert overtime.codigo == "OVERTIME"
        assert overtime.formula_tipo == "fijo"
        assert overtime.gravable is True
        assert overtime.activo is True


def test_load_income_concepts_is_idempotent(app, db_session):
    """
    Test that load_income_concepts() can be called multiple times safely.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_income_concepts() twice

    Verification:
        - No duplicate concepts are created
        - Concept count is correct after both calls
    """
    from coati_payroll.initial_data import load_income_concepts, INCOME_CONCEPTS
    from coati_payroll.model import Percepcion, db

    with app.app_context():
        # Load income concepts first time
        load_income_concepts()
        first_count = db.session.query(Percepcion).count()

        # Load income concepts second time
        load_income_concepts()
        second_count = db.session.query(Percepcion).count()

        # Count should be the same
        assert first_count == second_count
        assert first_count == len(INCOME_CONCEPTS)


def test_load_deduction_concepts_creates_concepts(app, db_session):
    """
    Test that load_deduction_concepts() creates deduction concept records.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_deduction_concepts()

    Verification:
        - Deduction concept records are created
        - At least SALARY_ADVANCE concept exists
        - Concept has correct attributes
    """
    from coati_payroll.initial_data import load_deduction_concepts
    from coati_payroll.model import Deduccion, db

    with app.app_context():
        # Load deduction concepts
        load_deduction_concepts()

        # Verify SALARY_ADVANCE concept exists
        salary_advance = db.session.execute(db.select(Deduccion).filter_by(codigo="SALARY_ADVANCE")).scalar_one_or_none()

        assert salary_advance is not None
        assert salary_advance.codigo == "SALARY_ADVANCE"
        assert salary_advance.tipo == "general"
        assert salary_advance.es_impuesto is False
        assert salary_advance.activo is True


def test_load_deduction_concepts_is_idempotent(app, db_session):
    """
    Test that load_deduction_concepts() can be called multiple times safely.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_deduction_concepts() twice

    Verification:
        - No duplicate concepts are created
        - Concept count is correct after both calls
    """
    from coati_payroll.initial_data import load_deduction_concepts, DEDUCTION_CONCEPTS
    from coati_payroll.model import Deduccion, db

    with app.app_context():
        # Load deduction concepts first time
        load_deduction_concepts()
        first_count = db.session.query(Deduccion).count()

        # Load deduction concepts second time
        load_deduction_concepts()
        second_count = db.session.query(Deduccion).count()

        # Count should be the same
        assert first_count == second_count
        assert first_count == len(DEDUCTION_CONCEPTS)


def test_load_benefit_concepts_creates_concepts(app, db_session):
    """
    Test that load_benefit_concepts() creates benefit concept records.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_benefit_concepts()

    Verification:
        - Benefit concept records are created
        - At least PAID_VACATION_PROVISION concept exists
        - Concept has correct attributes
    """
    from coati_payroll.initial_data import load_benefit_concepts
    from coati_payroll.model import Prestacion, db

    with app.app_context():
        # Load benefit concepts
        load_benefit_concepts()

        # Verify PAID_VACATION_PROVISION concept exists
        vacation_provision = (
            db.session.execute(db.select(Prestacion).filter_by(codigo="PAID_VACATION_PROVISION")).scalar_one_or_none()
        )

        assert vacation_provision is not None
        assert vacation_provision.codigo == "PAID_VACATION_PROVISION"
        assert vacation_provision.tipo == "patronal"
        assert vacation_provision.activo is True


def test_load_benefit_concepts_is_idempotent(app, db_session):
    """
    Test that load_benefit_concepts() can be called multiple times safely.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_benefit_concepts() twice

    Verification:
        - No duplicate concepts are created
        - Concept count is correct after both calls
    """
    from coati_payroll.initial_data import load_benefit_concepts, BENEFIT_CONCEPTS
    from coati_payroll.model import Prestacion, db

    with app.app_context():
        # Load benefit concepts first time
        load_benefit_concepts()
        first_count = db.session.query(Prestacion).count()

        # Load benefit concepts second time
        load_benefit_concepts()
        second_count = db.session.query(Prestacion).count()

        # Count should be the same
        assert first_count == second_count
        assert first_count == len(BENEFIT_CONCEPTS)


def test_load_payroll_types_creates_types(app, db_session):
    """
    Test that load_payroll_types() creates payroll type records.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_payroll_types()

    Verification:
        - Payroll type records are created
        - At least MONTHLY type exists
        - Type has correct attributes
    """
    from coati_payroll.initial_data import load_payroll_types
    from coati_payroll.model import TipoPlanilla, db

    with app.app_context():
        # Load payroll types
        load_payroll_types()

        # Verify MONTHLY type exists
        monthly = db.session.execute(db.select(TipoPlanilla).filter_by(codigo="MONTHLY")).scalar_one_or_none()

        assert monthly is not None
        assert monthly.codigo == "MONTHLY"
        assert monthly.dias == 30
        assert monthly.periodicidad == "mensual"
        assert monthly.periodos_por_anio == 12
        assert monthly.activo is True


def test_load_payroll_types_is_idempotent(app, db_session):
    """
    Test that load_payroll_types() can be called multiple times safely.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_payroll_types() twice

    Verification:
        - No duplicate types are created
        - Type count is correct after both calls
    """
    from coati_payroll.initial_data import load_payroll_types, PAYROLL_TYPES
    from coati_payroll.model import TipoPlanilla, db

    with app.app_context():
        # Load payroll types first time
        load_payroll_types()
        first_count = db.session.query(TipoPlanilla).count()

        # Load payroll types second time
        load_payroll_types()
        second_count = db.session.query(TipoPlanilla).count()

        # Count should be the same
        assert first_count == second_count
        assert first_count == len(PAYROLL_TYPES)


def test_load_initial_data_loads_all_data(app, db_session):
    """
    Test that load_initial_data() loads all initial data types.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_initial_data()

    Verification:
        - Currencies are loaded
        - Income concepts are loaded
        - Deduction concepts are loaded
        - Benefit concepts are loaded
        - Payroll types are loaded
    """
    from coati_payroll.initial_data import (
        load_initial_data,
        CURRENCIES,
        INCOME_CONCEPTS,
        DEDUCTION_CONCEPTS,
        BENEFIT_CONCEPTS,
        PAYROLL_TYPES,
    )
    from coati_payroll.model import Moneda, Percepcion, Deduccion, Prestacion, TipoPlanilla, db

    with app.app_context():
        # Load all initial data
        load_initial_data()

        # Verify all data types were loaded
        currency_count = db.session.query(Moneda).count()
        income_count = db.session.query(Percepcion).count()
        deduction_count = db.session.query(Deduccion).count()
        benefit_count = db.session.query(Prestacion).count()
        payroll_type_count = db.session.query(TipoPlanilla).count()

        assert currency_count == len(CURRENCIES)
        assert income_count == len(INCOME_CONCEPTS)
        assert deduction_count == len(DEDUCTION_CONCEPTS)
        assert benefit_count == len(BENEFIT_CONCEPTS)
        assert payroll_type_count == len(PAYROLL_TYPES)


def test_load_initial_data_is_idempotent(app, db_session):
    """
    Test that load_initial_data() can be called multiple times safely.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_initial_data() twice

    Verification:
        - No duplicate data is created
        - All counts remain the same after second call
    """
    from coati_payroll.initial_data import load_initial_data
    from coati_payroll.model import Moneda, Percepcion, Deduccion, Prestacion, TipoPlanilla, db

    with app.app_context():
        # Load initial data first time
        load_initial_data()
        first_currency_count = db.session.query(Moneda).count()
        first_income_count = db.session.query(Percepcion).count()
        first_deduction_count = db.session.query(Deduccion).count()
        first_benefit_count = db.session.query(Prestacion).count()
        first_payroll_type_count = db.session.query(TipoPlanilla).count()

        # Load initial data second time
        load_initial_data()
        second_currency_count = db.session.query(Moneda).count()
        second_income_count = db.session.query(Percepcion).count()
        second_deduction_count = db.session.query(Deduccion).count()
        second_benefit_count = db.session.query(Prestacion).count()
        second_payroll_type_count = db.session.query(TipoPlanilla).count()

        # All counts should remain the same
        assert first_currency_count == second_currency_count
        assert first_income_count == second_income_count
        assert first_deduction_count == second_deduction_count
        assert first_benefit_count == second_benefit_count
        assert first_payroll_type_count == second_payroll_type_count


def test_loaded_currencies_include_major_currencies(app, db_session):
    """
    Test that commonly used currencies are included in the loaded data.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_currencies()

    Verification:
        - USD, CAD, MXN, and other major currencies are present
    """
    from coati_payroll.initial_data import load_currencies
    from coati_payroll.model import Moneda, db

    with app.app_context():
        load_currencies()

        # Check for major currencies
        major_codes = ["USD", "CAD", "MXN", "BRL", "ARS"]
        for code in major_codes:
            currency = db.session.execute(db.select(Moneda).filter_by(codigo=code)).scalar_one_or_none()
            assert currency is not None, f"Currency {code} should be loaded"
            assert currency.activo is True


def test_loaded_income_concepts_include_common_types(app, db_session):
    """
    Test that commonly used income concepts are included in the loaded data.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_income_concepts()

    Verification:
        - OVERTIME, BONUSES, COMMISSIONS, etc. are present
    """
    from coati_payroll.initial_data import load_income_concepts
    from coati_payroll.model import Percepcion, db

    with app.app_context():
        load_income_concepts()

        # Check for common income concepts
        common_codes = ["OVERTIME", "BONUSES", "COMMISSIONS", "THIRTEENTH_SALARY"]
        for code in common_codes:
            concept = db.session.execute(db.select(Percepcion).filter_by(codigo=code)).scalar_one_or_none()
            assert concept is not None, f"Income concept {code} should be loaded"
            assert concept.activo is True


def test_loaded_deduction_concepts_include_common_types(app, db_session):
    """
    Test that commonly used deduction concepts are included in the loaded data.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_deduction_concepts()

    Verification:
        - SALARY_ADVANCE, ALIMONY, UNION_DUES, etc. are present
    """
    from coati_payroll.initial_data import load_deduction_concepts
    from coati_payroll.model import Deduccion, db

    with app.app_context():
        load_deduction_concepts()

        # Check for common deduction concepts
        common_codes = ["SALARY_ADVANCE", "ALIMONY", "UNION_DUES", "UNPAID_ABSENCES"]
        for code in common_codes:
            concept = db.session.execute(db.select(Deduccion).filter_by(codigo=code)).scalar_one_or_none()
            assert concept is not None, f"Deduction concept {code} should be loaded"
            assert concept.activo is True


def test_loaded_payroll_types_include_all_periodicities(app, db_session):
    """
    Test that all common payroll periodicities are included.

    Setup:
        - Use app and db_session fixtures

    Action:
        - Call load_payroll_types()

    Verification:
        - MONTHLY, BIWEEKLY, WEEKLY, etc. are present
        - Each has correct periods per year
    """
    from coati_payroll.initial_data import load_payroll_types
    from coati_payroll.model import TipoPlanilla, db

    with app.app_context():
        load_payroll_types()

        # Check for common payroll types with their expected periods
        expected_types = {
            "MONTHLY": 12,
            "BIWEEKLY": 24,
            "FORTNIGHTLY": 26,
            "WEEKLY": 52,
        }

        for code, expected_periods in expected_types.items():
            payroll_type = db.session.execute(db.select(TipoPlanilla).filter_by(codigo=code)).scalar_one_or_none()
            assert payroll_type is not None, f"Payroll type {code} should be loaded"
            assert payroll_type.periodos_por_anio == expected_periods
            assert payroll_type.activo is True
