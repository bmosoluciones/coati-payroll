# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Initial data for currencies, income concepts, deduction concepts, and payroll types.

This module provides default data to be loaded during system initialization.
All data is jurisdiction-agnostic and uses Flask-Babel for translation support.
Strings are marked for translation using _() and will be translated based on
the configured language in the database.
"""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.i18n import _l as _

# American currencies (North, Central, South America, and Caribbean)
# Currency names are marked for translation
CURRENCIES = [
    # North America
    {"codigo": "USD", "nombre": _("US Dollar"), "simbolo": "$"},
    {"codigo": "CAD", "nombre": _("Canadian Dollar"), "simbolo": "C$"},
    {"codigo": "MXN", "nombre": _("Mexican Peso"), "simbolo": "$"},
    # Central America
    {"codigo": "BZD", "nombre": _("Belize Dollar"), "simbolo": "BZ$"},
    {"codigo": "CRC", "nombre": _("Costa Rican Colón"), "simbolo": "₡"},
    {"codigo": "GTQ", "nombre": _("Guatemalan Quetzal"), "simbolo": "Q"},
    {"codigo": "HNL", "nombre": _("Honduran Lempira"), "simbolo": "L"},
    {"codigo": "NIO", "nombre": _("Nicaraguan Córdoba"), "simbolo": "C$"},
    {"codigo": "PAB", "nombre": _("Panamanian Balboa"), "simbolo": "B/."},
    {"codigo": "SVC", "nombre": _("Salvadoran Colón"), "simbolo": "₡"},
    # South America
    {"codigo": "ARS", "nombre": _("Argentine Peso"), "simbolo": "$"},
    {"codigo": "BOB", "nombre": _("Bolivian Boliviano"), "simbolo": "Bs."},
    {"codigo": "BRL", "nombre": _("Brazilian Real"), "simbolo": "R$"},
    {"codigo": "CLP", "nombre": _("Chilean Peso"), "simbolo": "$"},
    {"codigo": "COP", "nombre": _("Colombian Peso"), "simbolo": "$"},
    {"codigo": "GYD", "nombre": _("Guyanese Dollar"), "simbolo": "G$"},
    {"codigo": "PEN", "nombre": _("Peruvian Sol"), "simbolo": "S/"},
    {"codigo": "PYG", "nombre": _("Paraguayan Guaraní"), "simbolo": "₲"},
    {"codigo": "SRD", "nombre": _("Surinamese Dollar"), "simbolo": "$"},
    {"codigo": "UYU", "nombre": _("Uruguayan Peso"), "simbolo": "$"},
    {"codigo": "VES", "nombre": _("Venezuelan Bolívar"), "simbolo": "Bs."},
    # Caribbean
    {"codigo": "ANG", "nombre": _("Netherlands Antillean Guilder"), "simbolo": "ƒ"},
    {"codigo": "AWG", "nombre": _("Aruban Florin"), "simbolo": "ƒ"},
    {"codigo": "BBD", "nombre": _("Barbadian Dollar"), "simbolo": "$"},
    {"codigo": "BSD", "nombre": _("Bahamian Dollar"), "simbolo": "$"},
    {"codigo": "CUP", "nombre": _("Cuban Peso"), "simbolo": "$"},
    {"codigo": "DOP", "nombre": _("Dominican Peso"), "simbolo": "$"},
    {"codigo": "HTG", "nombre": _("Haitian Gourde"), "simbolo": "G"},
    {"codigo": "JMD", "nombre": _("Jamaican Dollar"), "simbolo": "J$"},
    {"codigo": "TTD", "nombre": _("Trinidad and Tobago Dollar"), "simbolo": "TT$"},
    {"codigo": "XCD", "nombre": _("East Caribbean Dollar"), "simbolo": "EC$"},
]


# Liquidation concepts (LiquidacionConcepto)
LIQUIDATION_CONCEPTS = [
    {
        "codigo": "DESPIDO",
        "nombre": _("Dismissal"),
        "descripcion": _("Termination initiated by employer"),
    },
    {
        "codigo": "RENUNCIA",
        "nombre": _("Resignation"),
        "descripcion": _("Termination initiated by employee"),
    },
]


# Income concepts (Percepciones / Ingresos)
# These add to employee salary
# All names and descriptions are marked for translation
INCOME_CONCEPTS = [
    {
        "codigo": "OVERTIME",
        "nombre": _("Overtime"),
        "descripcion": _("Additional hours worked beyond regular schedule"),
    },
    {
        "codigo": "COMMISSIONS",
        "nombre": _("Commissions"),
        "descripcion": _("Sales commissions and performance-based income"),
    },
    {
        "codigo": "BONUSES",
        "nombre": _("Bonuses"),
        "descripcion": _("Performance or achievement bonuses"),
    },
    {
        "codigo": "GOAL_INCENTIVES",
        "nombre": _("Goal Incentives"),
        "descripcion": _("Incentives for meeting specific targets or goals"),
    },
    {
        "codigo": "REPORTED_TIPS",
        "nombre": _("Reported Tips"),
        "descripcion": _("Tips and gratuities reported by employee"),
    },
    {
        "codigo": "TRANSPORT_ALLOWANCE",
        "nombre": _("Transportation Allowance"),
        "descripcion": _("Fixed transportation allowance"),
    },
    {
        "codigo": "FOOD_ALLOWANCE",
        "nombre": _("Food Allowance"),
        "descripcion": _("Fixed food or meal allowance"),
    },
    {
        "codigo": "HOUSING_ALLOWANCE",
        "nombre": _("Housing Allowance"),
        "descripcion": _("Fixed housing or rent allowance"),
    },
    {
        "codigo": "SENIORITY_BONUS",
        "nombre": _("Seniority Bonus"),
        "descripcion": _("Additional payment based on years of service"),
    },
    {
        "codigo": "PAID_VACATION",
        "nombre": _("Paid Vacation"),
        "descripcion": _("Payment for vacation time taken"),
    },
    {
        "codigo": "HOLIDAY_WORK",
        "nombre": _("Holiday Work"),
        "descripcion": _("Additional payment for working on holidays"),
    },
    {
        "codigo": "PAID_LEAVE",
        "nombre": _("Paid Leave"),
        "descripcion": _("Payment for authorized paid leave"),
    },
    {
        "codigo": "PAID_LICENSE",
        "nombre": _("Paid License"),
        "descripcion": _("Payment for extended paid license periods"),
    },
    {
        "codigo": "RETROACTIVE_PAYMENTS",
        "nombre": _("Retroactive Payments"),
        "descripcion": _("Back payments for salary adjustments"),
    },
    {
        "codigo": "THIRTEENTH_SALARY",
        "nombre": _("13th Month Salary"),
        "descripcion": _("Annual bonus (13th month salary)"),
    },
    {
        "codigo": "GRATUITIES",
        "nombre": _("Gratuities"),
        "descripcion": _("Discretionary bonuses or gratuities"),
    },
    {
        "codigo": "SEVERANCE_PAY",
        "nombre": _("Severance Pay"),
        "descripcion": _("Severance or termination compensation"),
    },
]


# Deduction concepts (Deducciones)
# These subtract from employee salary
# All names and descriptions are marked for translation
DEDUCTION_CONCEPTS = [
    {
        "codigo": "SALARY_ADVANCE",
        "nombre": _("Salary Advance"),
        "descripcion": _("Deduction for salary advance repayment (automatic from Loans/Advances module)"),
    },
    {
        "codigo": "VOLUNTARY_RETIREMENT",
        "nombre": _("Voluntary Retirement Plan"),
        "descripcion": _("Voluntary retirement savings contribution"),
    },
    {
        "codigo": "MEMBERSHIPS_SUBSCRIPTIONS",
        "nombre": _("Memberships/Subscriptions"),
        "descripcion": _("Deduction for memberships or subscription services"),
    },
    {
        "codigo": "CAFETERIA",
        "nombre": _("Cafeteria"),
        "descripcion": _("Company cafeteria charges"),
    },
    {
        "codigo": "INTERNAL_LOANS",
        "nombre": _("Internal Loans"),
        "descripcion": _("Internal loan repayment installments"),
    },
    {
        "codigo": "CREDIT_UNION_LOANS",
        "nombre": _("Credit Union Loans"),
        "descripcion": _("Credit union or cooperative loan payments"),
    },
    {
        "codigo": "LOAN_INTEREST",
        "nombre": _("Loan Interest"),
        "descripcion": _("Interest charges on loans"),
    },
    {
        "codigo": "ALIMONY",
        "nombre": _("Alimony"),
        "descripcion": _("Court-ordered alimony or child support payments"),
    },
    {
        "codigo": "COURT_GARNISHMENTS",
        "nombre": _("Court Garnishments"),
        "descripcion": _("Court-ordered wage garnishments"),
    },
    {
        "codigo": "UNPAID_ABSENCES",
        "nombre": _("Unpaid Absences"),
        "descripcion": _("Deductions for unpaid absences"),
    },
    {
        "codigo": "TARDINESS",
        "nombre": _("Tardiness"),
        "descripcion": _("Deductions for late arrivals"),
    },
    {
        "codigo": "NONCOMPLIANCE_PENALTIES",
        "nombre": _("Non-compliance Penalties"),
        "descripcion": _("Penalties for policy or contract violations"),
    },
    {
        "codigo": "LOSSES_DAMAGES",
        "nombre": _("Losses or Damages"),
        "descripcion": _("Deductions for lost or damaged property"),
    },
    {
        "codigo": "UNIFORM_PENALTIES",
        "nombre": _("Uniform Penalties"),
        "descripcion": _("Penalties for unreturned uniforms or equipment"),
    },
    {
        "codigo": "STORE_CANTEEN_PURCHASES",
        "nombre": _("Store/Canteen Purchases"),
        "descripcion": _("Purchases at company store or canteen"),
    },
    {
        "codigo": "VOLUNTARY_DONATIONS",
        "nombre": _("Voluntary Donations"),
        "descripcion": _("Voluntary charitable donations"),
    },
    {
        "codigo": "ASSOCIATION_CONTRIBUTIONS",
        "nombre": _("Association Contributions"),
        "descripcion": _("Voluntary contributions to associations"),
    },
    {
        "codigo": "UNION_DUES",
        "nombre": _("Union Dues"),
        "descripcion": _("Voluntary union membership dues"),
    },
    {
        "codigo": "OVERPAYMENT_CORRECTION",
        "nombre": _("Overpayment Correction"),
        "descripcion": _("Correction for previous overpayments"),
    },
]


# Employer benefit concepts (Prestaciones / Aportes Patronales)
# These are employer costs and provisions that do NOT affect employee's net pay
# All names and descriptions are marked for translation
BENEFIT_CONCEPTS = [
    {
        "codigo": "PAID_VACATION_PROVISION",
        "nombre": _("Paid Vacation Provision"),
        "descripcion": _("Employer provision for paid vacation days (universal labor right in the Americas)"),
    },
    {
        "codigo": "THIRTEENTH_SALARY_PROVISION",
        "nombre": _("13th Month Salary Provision"),
        "descripcion": _(
            "Employer provision for 13th month salary/Christmas bonus "
            "(aguinaldo - widespread right in Latin America)"
        ),
    },
    {
        "codigo": "SEVERANCE_PROVISION",
        "nombre": _("Severance Pay Provision"),
        "descripcion": _(
            "Employer provision for severance pay in case of unjust dismissal "
            "(common legal principle in the Americas)"
        ),
    },
]


# Payroll Types (Tipos de Planilla)
# Common payroll types with different periodicities
# All names and descriptions are marked for translation
PAYROLL_TYPES = [
    {
        "codigo": "MONTHLY",
        "descripcion": _("Monthly Payroll - 30 days"),
        "dias": 30,
        "periodicidad": "monthly",
        "periodos_por_anio": 12,
    },
    {
        "codigo": "BIWEEKLY",
        "descripcion": _("Biweekly Payroll - 15 days"),
        "dias": 15,
        "periodicidad": "biweekly",
        "periodos_por_anio": 24,
    },
    {
        "codigo": "FORTNIGHTLY",
        "descripcion": _("Fortnightly Payroll - 14 days"),
        "dias": 14,
        "periodicidad": "biweekly",
        "periodos_por_anio": 26,
    },
    {
        "codigo": "WEEKLY",
        "descripcion": _("Weekly Payroll - 7 days"),
        "dias": 7,
        "periodicidad": "weekly",
        "periodos_por_anio": 52,
    },
]


def load_currencies() -> None:
    """Load American currencies into the database.

    Currency names are translated based on the configured language in the database.
    This function is idempotent - it will not create duplicates on repeated calls.
    """
    from coati_payroll.model import Moneda, db
    from coati_payroll.log import log

    currencies_loaded = 0
    for currency_data in CURRENCIES:
        # Check if currency already exists
        existing = db.session.execute(db.select(Moneda).filter_by(codigo=currency_data["codigo"])).scalar_one_or_none()

        if existing is None:
            # Create new currency - nombre will be translated by _()
            # Convert lazy string to regular string for database storage
            currency = Moneda()
            currency.codigo = currency_data["codigo"]
            currency.nombre = str(currency_data["nombre"])
            currency.simbolo = currency_data["simbolo"]
            currency.activo = True

            db.session.add(currency)
            currencies_loaded += 1

    if currencies_loaded > 0:
        db.session.commit()
        log.trace("Loaded %s currencies", currencies_loaded)
    else:
        log.trace("No new currencies to load")


def load_income_concepts() -> None:
    """Load income concepts (percepciones) into the database.

    Concept names and descriptions are translated based on the configured
    language in the database. This function is idempotent.
    Default concepts are created with approved status.
    """
    from coati_payroll.model import Percepcion, db, utc_now
    from coati_payroll.enums import EstadoAprobacion
    from coati_payroll.log import log

    concepts_loaded = 0
    for concept_data in INCOME_CONCEPTS:
        # Check if concept already exists
        existing = db.session.execute(
            db.select(Percepcion).filter_by(codigo=concept_data["codigo"])
        ).scalar_one_or_none()

        if existing is None:
            # Create new income concept - strings will be translated by _()
            # Convert lazy strings to regular strings for database storage
            concept = Percepcion()
            concept.codigo = concept_data["codigo"]
            concept.nombre = str(concept_data["nombre"])
            concept.descripcion = str(concept_data["descripcion"])
            concept.formula_tipo = "fijo"
            concept.gravable = True
            concept.recurrente = False
            concept.activo = True
            concept.editable_en_nomina = True
            # Default concepts are pre-approved
            concept.estado_aprobacion = EstadoAprobacion.APROBADO
            concept.aprobado_por = "system"
            concept.aprobado_en = utc_now()
            concept.creado_por = "system"

            db.session.add(concept)
            concepts_loaded += 1

    if concepts_loaded > 0:
        db.session.commit()
        log.trace("Loaded %s income concepts", concepts_loaded)
    else:
        log.trace("No new income concepts to load")


def load_deduction_concepts() -> None:
    """Load deduction concepts (deducciones) into the database.

    Concept names and descriptions are translated based on the configured
    language in the database. This function is idempotent.
    Default concepts are created with approved status.
    """
    from coati_payroll.model import Deduccion, db, utc_now
    from coati_payroll.enums import EstadoAprobacion
    from coati_payroll.log import log

    concepts_loaded = 0
    for concept_data in DEDUCTION_CONCEPTS:
        # Check if concept already exists
        existing = db.session.execute(
            db.select(Deduccion).filter_by(codigo=concept_data["codigo"])
        ).scalar_one_or_none()

        if existing is None:
            # Create new deduction concept - strings will be translated by _()
            # Convert lazy strings to regular strings for database storage
            concept = Deduccion()
            concept.codigo = concept_data["codigo"]
            concept.nombre = str(concept_data["nombre"])
            concept.descripcion = str(concept_data["descripcion"])
            concept.tipo = "general"
            concept.es_impuesto = False
            concept.formula_tipo = "fijo"
            concept.antes_impuesto = False
            concept.recurrente = False
            concept.activo = True
            concept.editable_en_nomina = True
            # Default concepts are pre-approved
            concept.estado_aprobacion = EstadoAprobacion.APROBADO
            concept.aprobado_por = "system"
            concept.aprobado_en = utc_now()
            concept.creado_por = "system"

            db.session.add(concept)
            concepts_loaded += 1

    if concepts_loaded > 0:
        db.session.commit()
        log.trace("Loaded %s deduction concepts", concepts_loaded)
    else:
        log.trace("No new deduction concepts to load")


def load_benefit_concepts() -> None:
    """Load employer benefit concepts (prestaciones) into the database.

    Concept names and descriptions are translated based on the configured
    language in the database. This function is idempotent.
    Default concepts are created with approved status.
    """
    from coati_payroll.model import Prestacion, db, utc_now
    from coati_payroll.enums import EstadoAprobacion
    from coati_payroll.log import log

    concepts_loaded = 0
    for concept_data in BENEFIT_CONCEPTS:
        # Check if concept already exists
        existing = db.session.execute(
            db.select(Prestacion).filter_by(codigo=concept_data["codigo"])
        ).scalar_one_or_none()

        if existing is None:
            # Create new benefit concept - strings will be translated by _()
            # Convert lazy strings to regular strings for database storage
            concept = Prestacion()
            concept.codigo = concept_data["codigo"]
            concept.nombre = str(concept_data["nombre"])
            concept.descripcion = str(concept_data["descripcion"])
            concept.tipo = "employer"
            concept.formula_tipo = "fixed"
            concept.recurrente = False
            concept.activo = True
            concept.editable_en_nomina = True
            # Default concepts are pre-approved
            concept.estado_aprobacion = EstadoAprobacion.APROBADO
            concept.aprobado_por = "system"
            concept.aprobado_en = utc_now()
            concept.creado_por = "system"

            db.session.add(concept)
            concepts_loaded += 1

    if concepts_loaded > 0:
        db.session.commit()
        log.trace("Loaded %s benefit concepts", concepts_loaded)
    else:
        log.trace("No new benefit concepts to load")


def load_payroll_types() -> None:
    """Load common payroll types into the database.

    Payroll type descriptions are translated based on the configured
    language in the database. This function is idempotent.
    """
    from coati_payroll.model import TipoPlanilla, db
    from coati_payroll.log import log

    types_loaded = 0
    for type_data in PAYROLL_TYPES:
        # Check if payroll type already exists
        existing = db.session.execute(
            db.select(TipoPlanilla).filter_by(codigo=type_data["codigo"])
        ).scalar_one_or_none()

        if existing is None:
            # Create new payroll type - strings will be translated by _()
            # Convert lazy strings to regular strings for database storage
            payroll_type = TipoPlanilla()
            payroll_type.codigo = type_data["codigo"]
            payroll_type.descripcion = str(type_data["descripcion"])
            payroll_type.dias = type_data["dias"]
            payroll_type.periodicidad = type_data["periodicidad"]
            payroll_type.periodos_por_anio = type_data["periodos_por_anio"]
            payroll_type.mes_inicio_fiscal = 1  # January
            payroll_type.dia_inicio_fiscal = 1  # 1st day
            payroll_type.acumula_anual = True
            payroll_type.activo = True

            db.session.add(payroll_type)
            types_loaded += 1

    if types_loaded > 0:
        db.session.commit()
        log.trace("Loaded %s payroll types", types_loaded)
    else:
        log.trace("No new payroll types to load")


def load_liquidation_concepts() -> None:
    """Load liquidation concepts into the database.

    This function is idempotent.
    """
    from coati_payroll.model import LiquidacionConcepto, db
    from coati_payroll.log import log

    concepts_loaded = 0
    for concept_data in LIQUIDATION_CONCEPTS:
        existing = db.session.execute(
            db.select(LiquidacionConcepto).filter_by(codigo=concept_data["codigo"])
        ).scalar_one_or_none()

        if existing is None:
            concept = LiquidacionConcepto()
            concept.codigo = concept_data["codigo"]
            concept.nombre = str(concept_data["nombre"])
            concept.descripcion = str(concept_data["descripcion"])
            concept.activo = True
            db.session.add(concept)
            concepts_loaded += 1

    if concepts_loaded > 0:
        db.session.commit()
        log.trace("Loaded %s liquidation concepts", concepts_loaded)
    else:
        log.trace("No new liquidation concepts to load")


def load_initial_data() -> None:
    """Load all initial data into the database.

    This function loads currencies, income concepts, deduction concepts,
    employer benefit concepts, and payroll types. All strings are translated
    based on the configured language in the database.
    This function is idempotent - safe to call multiple times.
    """
    from coati_payroll.log import log

    log.trace("Loading initial data")

    load_currencies()
    load_income_concepts()
    load_deduction_concepts()
    load_benefit_concepts()
    load_payroll_types()
    load_liquidation_concepts()

    log.trace("Initial data loading completed")
