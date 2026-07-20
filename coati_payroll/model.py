# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Data model for the payroll module."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from decimal import Decimal
from datetime import date, datetime, timezone

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
import orjson
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import TypeDecorator, JSON
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import validates
from ulid import ULID

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #

from coati_payroll.enums import (
    AccrualFrequency,
    AccrualMethod,
    AdelantoEstado,
    CargaInicialEstado,
    EstadoAprobacion,
    LiquidacionEstado,
    NominaEstado,
    Periodicidad,
    TipoAcumulacionPrestacion,
    TipoUsuario,
)

db = SQLAlchemy()
database = db


# -----------------------[ UTILITY FUNCTIONS ]----------------------- #
def _orjson_default(value):
    """Default serializer for non-native JSON types."""
    if isinstance(value, Decimal):
        # Keep exact decimal representation for financial values.
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def generador_de_codigos_unicos() -> str:
    """Genera codigo unicos basados en ULID."""

    codigo_aleatorio = ULID()
    id_unico = str(codigo_aleatorio)

    return id_unico


def generador_codigo_empleado() -> str:
    """Genera código único de empleado.

    Formato: EMP-XXXXXX donde X es alfanumérico.
    Usa los últimos 6 caracteres del ULID para unicidad.
    """
    codigo_aleatorio = ULID()
    sufijo = str(codigo_aleatorio)[-6:].upper()
    return f"EMP-{sufijo}"


def utc_now() -> datetime:
    """Generate timezone-aware UTC datetime.

    Replacement for deprecated datetime.utcnow() with timezone-aware alternative.
    """
    return datetime.now(timezone.utc)


# ----------------------[ GLOBAL VARIABLES DEFINITION ]---------------------- #
FK_MONEDA_ID = "moneda.id"
FK_EMPRESA_ID = "empresa.id"
FK_PLANILLA_ID = "planilla.id"
FK_PERCEPCION_ID = "percepcion.id"
FK_DEDUCCION_ID = "deduccion.id"
FK_PRESTACION_ID = "prestacion.id"
FK_EMPLEADO_ID = "empleado.id"
FK_NOMINA_ID = "nomina.id"
FK_REPORT_ID = "report.id"


# Utiliza orjon para serializar/deserializar JSON
class OrjsonType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return orjson.dumps(value, default=_orjson_default).decode("utf-8")
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if isinstance(value, (dict, list)):
                return value  # PostgreSQL ya lo deserializó
            return orjson.loads(value)
        return value


# Clase base para todas las tablas
class BaseTabla:
    """Columnas estandar para todas las tablas de la base de datos."""

    # Pistas de auditoria comunes a todas las tablas.
    id = database.Column(
        database.String(26),
        primary_key=True,
        nullable=False,
        index=True,
        default=generador_de_codigos_unicos,
    )
    timestamp = database.Column(database.DateTime, default=utc_now, nullable=False)
    creado = database.Column(database.Date, default=date.today, nullable=False)
    creado_por = database.Column(database.String(150), nullable=True)
    modificado = database.Column(database.DateTime, onupdate=utc_now, nullable=True)
    modificado_por = database.Column(database.String(150), nullable=True)


class PluginRegistry(database.Model, BaseTabla):
    __tablename__ = "plugin_registry"
    __table_args__ = (database.UniqueConstraint("distribution_name", name="uq_plugin_distribution_name"),)

    distribution_name = database.Column(database.String(200), nullable=False, unique=True, index=True)
    plugin_id = database.Column(database.String(200), nullable=False, index=True)
    version = database.Column(database.String(50), nullable=True)
    active = database.Column(database.Boolean(), default=False, nullable=False)
    installed = database.Column(database.Boolean(), default=True, nullable=False)


# Gestión de usuarios con acceso a la aplicación
class Usuario(database.Model, BaseTabla, UserMixin):
    __tablename__ = "usuario"
    __table_args__ = (
        database.UniqueConstraint("usuario", name="id_usuario_unico"),
        database.UniqueConstraint("correo_electronico", name="correo_usuario_unico"),
    )

    usuario = database.Column(database.String(150), nullable=False, index=True, unique=True)
    acceso = database.Column(database.LargeBinary(), nullable=False)
    nombre = database.Column(database.String(100))
    apellido = database.Column(database.String(100))
    correo_electronico = database.Column(database.String(150))
    tipo = database.Column(database.String(20), nullable=False, default=TipoUsuario.HHRR.value)
    activo = database.Column(database.Boolean(), default=True)
    ultimo_acceso = database.Column(database.DateTime, nullable=True)

    @validates("tipo")
    def validate_tipo(self, key, value):
        """Normalize and validate user role values."""
        if value is None:
            raise ValueError("Invalid role: None")
        if isinstance(value, TipoUsuario):
            return value.value
        if isinstance(value, str):
            normalized = value.strip().lower()
            allowed_values = {role.value for role in TipoUsuario}
            if normalized in allowed_values:
                return normalized
        raise ValueError(f"Invalid role: {value}")


# Gestión de empresas/entidades
class Empresa(database.Model, BaseTabla):
    """Company/Entity model for multi-company support.

    Allows the payroll system to handle multiple companies/entities.
    Employees and Payrolls are associated with a company.
    Deductions, Benefits, and Perceptions remain independent and can be used
    across multiple companies.
    """

    __tablename__ = "empresa"
    __table_args__ = (
        database.UniqueConstraint("codigo", name="uq_empresa_codigo"),
        database.UniqueConstraint("ruc", name="uq_empresa_ruc"),
    )

    # Unique company code
    codigo = database.Column(database.String(50), unique=True, nullable=False, index=True)

    # Company legal name
    razon_social = database.Column(database.String(200), nullable=False)

    # Commercial/trade name
    nombre_comercial = database.Column(database.String(200), nullable=True)

    # Tax identification number (jurisdiction-specific format)
    ruc = database.Column(database.String(50), unique=True, nullable=False)

    # Contact information
    direccion = database.Column(database.String(255), nullable=True)
    telefono = database.Column(database.String(50), nullable=True)
    correo = database.Column(database.String(150), nullable=True)
    sitio_web = database.Column(database.String(200), nullable=True)

    # Legal representative
    representante_legal = database.Column(database.String(150), nullable=True)

    # Status
    activo = database.Column(database.Boolean(), default=True, nullable=False)

    # Initial payroll implementation period for company-level mid-year carry-in
    primer_mes_nomina = database.Column(database.Integer, nullable=True, default=lambda: date.today().month)
    primer_anio_nomina = database.Column(database.Integer, nullable=True, default=lambda: date.today().year)

    # Accounting control for base salary at company level
    codigo_cuenta_debe_salario = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_debe_salario = database.Column(database.String(255), nullable=True)
    codigo_cuenta_haber_salario = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_haber_salario = database.Column(database.String(255), nullable=True)

    # Relationships
    empleados = database.relationship("Empleado", back_populates="empresa")
    planillas = database.relationship("Planilla", back_populates="empresa")


# Gestión de monedas y tipos de cambio
class Moneda(database.Model, BaseTabla):
    __tablename__ = "moneda"

    codigo = database.Column(database.String(10), unique=True, nullable=False, index=True)
    nombre = database.Column(database.String(100), nullable=False)
    simbolo = database.Column(database.String(10), nullable=True)
    activo = database.Column(database.Boolean(), default=True)

    # relaciones
    planillas = database.relationship("Planilla", back_populates="moneda")
    empleados = database.relationship("Empleado", back_populates="moneda")
    tipo_cambio_origen = database.relationship(
        "TipoCambio",
        back_populates="moneda_origen",
        foreign_keys="TipoCambio.moneda_origen_id",
    )
    tipo_cambio_destino = database.relationship(
        "TipoCambio",
        back_populates="moneda_destino",
        foreign_keys="TipoCambio.moneda_destino_id",
    )


class TipoCambio(database.Model, BaseTabla):
    __tablename__ = "tipo_cambio"
    __table_args__ = (
        database.UniqueConstraint(
            "moneda_origen_id",
            "moneda_destino_id",
            "fecha",
            name="uq_tc_origen_destino_fecha",
        ),
    )

    fecha = database.Column(database.Date, nullable=False, default=date.today, index=True)
    moneda_origen_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=False)
    moneda_destino_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=False)
    tasa = database.Column(database.Numeric(24, 10), nullable=False)

    moneda_origen = database.relationship(
        "Moneda", back_populates="tipo_cambio_origen", foreign_keys=[moneda_origen_id]
    )
    moneda_destino = database.relationship(
        "Moneda", back_populates="tipo_cambio_destino", foreign_keys=[moneda_destino_id]
    )


# Registro maestro de empleados
class Empleado(database.Model, BaseTabla):
    __tablename__ = "empleado"
    __table_args__ = (
        database.UniqueConstraint("identificacion_personal", name="uq_empleado_identificacion"),
        database.UniqueConstraint("codigo_empleado", name="uq_empleado_codigo"),
    )

    # Código único de empleado (auto-generado si no se proporciona)
    codigo_empleado = database.Column(
        database.String(20),
        unique=True,
        nullable=False,
        index=True,
        default=generador_codigo_empleado,
    )

    primer_nombre = database.Column(database.String(100), nullable=False)
    segundo_nombre = database.Column(database.String(100), nullable=True)
    primer_apellido = database.Column(database.String(100), nullable=False)
    segundo_apellido = database.Column(database.String(100), nullable=True)

    genero = database.Column(database.String(20), nullable=True)
    nacionalidad = database.Column(database.String(100), nullable=True)
    tipo_identificacion = database.Column(database.String(50), nullable=True)
    identificacion_personal = database.Column(database.String(50), unique=True, nullable=False)
    id_seguridad_social = database.Column(database.String(50), nullable=True)
    id_fiscal = database.Column(database.String(50), nullable=True)
    tipo_sangre = database.Column(database.String(10), nullable=True)
    fecha_nacimiento = database.Column(database.Date, nullable=True)

    fecha_alta = database.Column(database.Date, nullable=False, default=date.today)
    fecha_baja = database.Column(database.Date, nullable=True)
    activo = database.Column(database.Boolean(), default=True, nullable=False)

    cargo = database.Column(database.String(150), nullable=True)
    area = database.Column(database.String(150), nullable=True)
    centro_costos = database.Column(database.String(150), nullable=True)

    salario_base = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Moneda del sueldo: FK hacia moneda.id (consistencia)
    moneda_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=True)
    moneda = database.relationship("Moneda", back_populates="empleados")

    # Empresa a la que pertenece el empleado
    empresa_id = database.Column(database.String(26), database.ForeignKey(FK_EMPRESA_ID), nullable=True)
    empresa = database.relationship("Empresa", back_populates="empleados")

    correo = database.Column(database.String(150), nullable=True, index=True)
    telefono = database.Column(database.String(50), nullable=True)
    direccion = database.Column(database.String(255), nullable=True)
    estado_civil = database.Column(database.String(50), nullable=True)
    banco = database.Column(database.String(100), nullable=True)
    numero_cuenta_bancaria = database.Column(database.String(100), nullable=True)

    tipo_contrato = database.Column(database.String(50), nullable=True)
    fecha_ultimo_aumento = database.Column(database.Date, nullable=True)

    # Datos iniciales de implementación
    # Estos campos almacenan saldos acumulados cuando el sistema se implementa
    # a mitad de un período fiscal
    salario_acumulado = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    impuesto_acumulado = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    ultimos_tres_salarios = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    # relaciones
    planilla_asociaciones = database.relationship(
        "PlanillaEmpleado",
        back_populates="empleado",
    )
    nominas = database.relationship(
        "NominaEmpleado",
        back_populates="empleado",
    )
    novedades_registradas = database.relationship(
        "NominaNovedad", back_populates="empleado", cascade="all,delete-orphan"
    )
    historial_salarios = database.relationship(
        "HistorialSalario", back_populates="empleado", cascade="all,delete-orphan"
    )
    vacaciones = database.relationship("VacacionEmpleado", back_populates="empleado", cascade="all,delete-orphan")
    vacaciones_descansadas = database.relationship(
        "VacacionDescansada", back_populates="empleado", cascade="all,delete-orphan"
    )
    adelantos = database.relationship("Adelanto", back_populates="empleado", cascade="all,delete-orphan")

    # Datos adicionales (JSON)
    datos_adicionales = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)


# Gestión de planillas
class TipoPlanilla(database.Model, BaseTabla):
    """Payroll type configuration.

    Defines the type of payroll (monthly, biweekly, weekly, etc.) and its
    fiscal period parameters. The fiscal period can be different from the
    calendar year (Jan-Dec) and is defined here to support various accounting
    requirements.
    """

    __tablename__ = "tipo_planilla"

    codigo = database.Column(database.String(40), unique=True, nullable=False)
    descripcion = database.Column(database.String(150), nullable=True)
    dias = database.Column(database.Integer, nullable=False, default=30)  # días usados para prorrateos
    periodicidad = database.Column(
        database.String(20), nullable=False, default=Periodicidad.MENSUAL
    )  # ej. mensual, quincenal, semanal

    # Fiscal period configuration
    # mes_inicio_fiscal: Month when the fiscal year starts (1-12)
    mes_inicio_fiscal = database.Column(database.Integer, nullable=False, default=1)  # 1 = January
    # dia_inicio_fiscal: Day of month when fiscal year starts
    dia_inicio_fiscal = database.Column(database.Integer, nullable=False, default=1)

    # Accumulated calculation settings
    # acumula_anual: Whether this payroll type accumulates values annually
    acumula_anual = database.Column(database.Boolean(), default=True, nullable=False)
    # periodos_por_anio: Number of payroll periods per fiscal year
    periodos_por_anio = database.Column(database.Integer, nullable=False, default=12)

    # Tax calculation parameters (stored as JSON for flexibility)
    parametros_calculo = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    activo = database.Column(database.Boolean(), default=True, nullable=False)

    planillas = database.relationship("Planilla", back_populates="tipo_planilla")
    acumulados = database.relationship("AcumuladoAnual", back_populates="tipo_planilla")


class Planilla(database.Model, BaseTabla):
    """Master payroll record that connects employees, perceptions, deductions, and benefits.

    The Planilla acts as the central hub for payroll configuration:
    - Employees assigned via PlanillaEmpleado
    - Perceptions via PlanillaIngreso
    - Deductions via PlanillaDeduccion (with priority order)
    - Benefits via PlanillaPrestacion
    - Calculation rules via PlanillaReglaCalculo

    Automatic Deductions:
    The payroll engine automatically applies loan installments and salary advances
    from the Adelanto table for employees with active loans, regardless of whether
    those deductions are explicitly configured in planilla_deducciones.
    The priority for these automatic deductions is controlled by:
    - prioridad_prestamos: Priority for loan installments
    - prioridad_adelantos: Priority for salary advances
    """

    __tablename__ = "planilla"

    nombre = database.Column(database.String(150), nullable=False, unique=True)
    descripcion = database.Column(database.String(255), nullable=True)
    activo = database.Column(database.Boolean(), default=True, nullable=False)

    parametros = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    tipo_planilla_id = database.Column(database.String(26), database.ForeignKey("tipo_planilla.id"), nullable=False)
    tipo_planilla = database.relationship("TipoPlanilla", back_populates="planillas")

    moneda_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=False)
    moneda = database.relationship("Moneda", back_populates="planillas")

    # Empresa a la que pertenece la planilla
    empresa_id = database.Column(database.String(26), database.ForeignKey(FK_EMPRESA_ID), nullable=True)
    empresa = database.relationship("Empresa", back_populates="planillas")

    # Strong relationship: each payroll can bind to one specific vacation accrual policy
    vacation_policy_id = database.Column(
        database.String(26),
        database.ForeignKey("vacation_policy.id", name="fk_planilla_vacation_policy_id"),
        nullable=True,
        index=True,
    )
    vacation_policy = database.relationship("VacationPolicy", foreign_keys=[vacation_policy_id])

    # Período Fiscal
    # Fuente de verdad por planilla para el mes de inicio fiscal (1=enero ... 12=diciembre)
    mes_inicio_fiscal = database.Column(database.Integer, nullable=False, default=1)
    periodo_fiscal_inicio = database.Column(database.Date, nullable=True)
    periodo_fiscal_fin = database.Column(database.Date, nullable=True)

    # Ultima ejecución
    ultima_ejecucion = database.Column(database.DateTime, nullable=True)

    # Automatic deduction priorities (applied even if not in planilla_deducciones)
    # Loans and advances from Adelanto table are automatically deducted
    # Lower number = higher priority (applied first)
    prioridad_prestamos = database.Column(
        database.Integer, nullable=False, default=250
    )  # Default: after mandatory deductions
    prioridad_adelantos = database.Column(database.Integer, nullable=False, default=251)  # Default: right after loans

    # Whether to apply automatic loan/advance deductions
    aplicar_prestamos_automatico = database.Column(database.Boolean(), default=True, nullable=False)
    aplicar_adelantos_automatico = database.Column(database.Boolean(), default=True, nullable=False)

    # Accounting control for base salary
    # Base salary is the foundation of payroll calculation and needs its own
    # accounting accounts to generate proper accounting vouchers
    codigo_cuenta_debe_salario = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_debe_salario = database.Column(database.String(255), nullable=True)
    codigo_cuenta_haber_salario = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_haber_salario = database.Column(database.String(255), nullable=True)

    # relaciones con componentes configurados
    planilla_percepciones = database.relationship(
        "PlanillaIngreso",
        back_populates="planilla",
    )
    planilla_deducciones = database.relationship(
        "PlanillaDeduccion",
        back_populates="planilla",
    )
    planilla_prestaciones = database.relationship(
        "PlanillaPrestacion",
        back_populates="planilla",
    )

    # reglas de cálculo asociadas (impuestos, fórmulas complejas)
    planilla_reglas_calculo = database.relationship(
        "PlanillaReglaCalculo",
        back_populates="planilla",
    )

    # empleados asignados a la planilla (config)
    planilla_empleados = database.relationship(
        "PlanillaEmpleado",
        back_populates="planilla",
    )

    # Audit and governance fields
    estado_aprobacion = database.Column(
        database.String(20), nullable=False, default=EstadoAprobacion.BORRADOR, index=True
    )
    aprobado_por = database.Column(database.String(150), nullable=True)
    aprobado_en = database.Column(database.DateTime, nullable=True)
    creado_por_plugin = database.Column(database.Boolean(), default=False, nullable=False)
    plugin_source = database.Column(database.String(200), nullable=True)

    # ejecuciones históricas (nominas)
    nominas = database.relationship(
        "Nomina",
        back_populates="planilla",
    )
    audit_logs = database.relationship(
        "PlanillaAuditLog",
        back_populates="planilla",
        cascade="all, delete-orphan",
    )


# Percepciones y deducciones - THESE AFFECT EMPLOYEE'S NET PAY
# Percepciones (ingresos) se SUMAN al salario
# Deducciones se RESTAN del salario
class Percepcion(database.Model, BaseTabla):
    """Income items that ADD to employee's pay.

    Percepciones are income items that increase the employee's gross salary.
    Examples: base salary, overtime, bonuses, commissions, allowances.

    Together with Deducciones, these determine the employee's net pay.
    (Prestaciones do NOT affect employee pay - they are employer costs.)
    """

    __tablename__ = "percepcion"

    codigo = database.Column(database.String(50), unique=True, nullable=False, index=True)
    nombre = database.Column(database.String(150), nullable=False)
    descripcion = database.Column(database.String(255), nullable=True)

    # tipo de cálculo: 'fijo', 'porcentaje_salario', 'porcentaje_bruto', 'formula', 'horas', etc.
    formula_tipo = database.Column(database.String(50), nullable=False, default="fixed")
    monto_default = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    formula = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    condicion = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    porcentaje = database.Column(database.Numeric(5, 2), nullable=True)
    gravable = database.Column(database.Boolean(), default=True)
    recurrente = database.Column(database.Boolean(), default=False)
    activo = database.Column(database.Boolean(), default=True)

    # Vigencia: hasta cuándo es válida esta percepción (opcional)
    vigente_desde = database.Column(database.Date, nullable=True)  # opcional, si quieres rango
    valido_hasta = database.Column(database.Date, nullable=True)

    # Especificidad de cálculo
    base_calculo = database.Column(  # ej: 'salario_base', 'gravable', 'bruto', 'neto'
        database.String(50), nullable=True
    )
    unidad_calculo = database.Column(database.String(20), nullable=True)  # ej: 'horas', 'dias', None

    # Control contable
    contabilizable = database.Column(database.Boolean(), default=True, nullable=False)
    invertir_asiento_contable = database.Column(database.Boolean(), default=False, nullable=False)
    codigo_cuenta_debe = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_debe = database.Column(database.String(255), nullable=True)
    codigo_cuenta_haber = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_haber = database.Column(database.String(255), nullable=True)
    mostrar_como_ingreso_reportes = database.Column(database.Boolean(), default=True, nullable=False)

    # Control edición en nómina
    editable_en_nomina = database.Column(database.Boolean(), default=False, nullable=False)

    # Defaults de tratamiento de inasistencias al crear novedades
    es_inasistencia = database.Column(database.Boolean(), default=False, nullable=False)
    descontar_pago_inasistencia = database.Column(database.Boolean(), default=False, nullable=False)

    # Audit and governance fields
    estado_aprobacion = database.Column(
        database.String(20), nullable=False, default=EstadoAprobacion.BORRADOR, index=True
    )
    aprobado_por = database.Column(database.String(150), nullable=True)
    aprobado_en = database.Column(database.DateTime, nullable=True)
    creado_por_plugin = database.Column(database.Boolean(), default=False, nullable=False)
    plugin_source = database.Column(database.String(200), nullable=True)

    planillas = database.relationship(
        "PlanillaIngreso",
        back_populates="percepcion",
    )
    nomina_detalles = database.relationship("NominaDetalle", back_populates="percepcion")
    audit_logs = database.relationship(
        "ConceptoAuditLog",
        back_populates="percepcion",
        foreign_keys="ConceptoAuditLog.percepcion_id",
        cascade="all, delete-orphan",
    )


class Deduccion(database.Model, BaseTabla):
    __tablename__ = "deduccion"

    codigo = database.Column(database.String(50), unique=True, nullable=False, index=True)
    nombre = database.Column(database.String(150), nullable=False)
    descripcion = database.Column(database.String(255), nullable=True)

    tipo = database.Column(database.String(30), nullable=False, default="general")
    es_impuesto = database.Column(database.Boolean(), default=False)

    formula_tipo = database.Column(database.String(50), nullable=False, default="fixed")
    monto_default = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    formula = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    condicion = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    porcentaje = database.Column(database.Numeric(5, 2), nullable=True)
    antes_impuesto = database.Column(database.Boolean(), default=True)
    recurrente = database.Column(database.Boolean(), default=False)
    activo = database.Column(database.Boolean(), default=True)

    # Vigencia
    vigente_desde = database.Column(database.Date, nullable=True)
    valido_hasta = database.Column(database.Date, nullable=True)

    # Base y unidad de cálculo
    base_calculo = database.Column(database.String(50), nullable=True)
    unidad_calculo = database.Column(database.String(20), nullable=True)

    # Control contable
    contabilizable = database.Column(database.Boolean(), default=True, nullable=False)
    invertir_asiento_contable = database.Column(database.Boolean(), default=False, nullable=False)
    codigo_cuenta_debe = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_debe = database.Column(database.String(255), nullable=True)
    codigo_cuenta_haber = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_haber = database.Column(database.String(255), nullable=True)
    mostrar_como_ingreso_reportes = database.Column(database.Boolean(), default=True, nullable=False)

    # Control edición en nómina
    editable_en_nomina = database.Column(database.Boolean(), default=False, nullable=False)

    # Defaults de tratamiento de inasistencias al crear novedades
    es_inasistencia = database.Column(database.Boolean(), default=False, nullable=False)
    descontar_pago_inasistencia = database.Column(database.Boolean(), default=False, nullable=False)

    # Audit and governance fields
    estado_aprobacion = database.Column(
        database.String(20), nullable=False, default=EstadoAprobacion.BORRADOR, index=True
    )
    aprobado_por = database.Column(database.String(150), nullable=True)
    aprobado_en = database.Column(database.DateTime, nullable=True)
    creado_por_plugin = database.Column(database.Boolean(), default=False, nullable=False)
    plugin_source = database.Column(database.String(200), nullable=True)

    planillas = database.relationship(
        "PlanillaDeduccion",
        back_populates="deduccion",
    )
    nomina_detalles = database.relationship("NominaDetalle", back_populates="deduccion")
    tablas_impuesto = database.relationship("TablaImpuesto", back_populates="deduccion")
    adelantos = database.relationship("Adelanto", back_populates="deduccion")
    audit_logs = database.relationship(
        "ConceptoAuditLog",
        back_populates="deduccion",
        foreign_keys="ConceptoAuditLog.deduccion_id",
        cascade="all, delete-orphan",
    )


# Prestaciones (aportes del empleador: seguridad social, etc.)
# NOTA: Las prestaciones son costos patronales que NO afectan el pago al empleado.
# Solo las percepciones y deducciones afectan el salario neto del empleado.
# Ejemplos de prestaciones: INSS patronal, provisión de vacaciones, aguinaldo, indemnización.
class Prestacion(database.Model, BaseTabla):
    """Employer contributions and provisions.

    Prestaciones are employer costs that do NOT affect the employee's net pay.
    They represent the company's obligations such as:
    - Social security employer contributions (INSS patronal)
    - Vacation provisions
    - 13th month (aguinaldo) provisions
    - Severance provisions (indemnización)

    Only Percepciones (income) and Deducciones affect the employee's net salary.
    """

    __tablename__ = "prestacion"

    codigo = database.Column(database.String(50), unique=True, nullable=False, index=True)
    nombre = database.Column(database.String(150), nullable=False)
    descripcion = database.Column(database.String(255), nullable=True)

    tipo = database.Column(database.String(30), nullable=False, default="employer")

    formula_tipo = database.Column(database.String(50), nullable=False, default="fixed")
    monto_default = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    formula = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    condicion = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    porcentaje = database.Column(database.Numeric(5, 2), nullable=True)
    recurrente = database.Column(database.Boolean(), default=False)
    activo = database.Column(database.Boolean(), default=True)

    vigente_desde = database.Column(database.Date, nullable=True)
    valido_hasta = database.Column(database.Date, nullable=True)

    base_calculo = database.Column(database.String(50), nullable=True)
    unidad_calculo = database.Column(database.String(20), nullable=True)

    tope_aplicacion = database.Column(database.Numeric(14, 2), nullable=True)

    contabilizable = database.Column(database.Boolean(), default=True, nullable=False)
    codigo_cuenta_debe = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_debe = database.Column(database.String(255), nullable=True)
    codigo_cuenta_haber = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_haber = database.Column(database.String(255), nullable=True)

    editable_en_nomina = database.Column(database.Boolean(), default=False, nullable=False)

    # Accumulation configuration
    # Defines how this benefit accumulates: monthly settlement, annually, or lifetime
    tipo_acumulacion = database.Column(
        database.String(20), nullable=False, default=TipoAcumulacionPrestacion.MENSUAL
    )  # monthly | annual | lifetime

    # Audit and governance fields
    estado_aprobacion = database.Column(
        database.String(20), nullable=False, default=EstadoAprobacion.BORRADOR, index=True
    )
    aprobado_por = database.Column(database.String(150), nullable=True)
    aprobado_en = database.Column(database.DateTime, nullable=True)
    creado_por_plugin = database.Column(database.Boolean(), default=False, nullable=False)
    plugin_source = database.Column(database.String(200), nullable=True)

    planillas = database.relationship(
        "PlanillaPrestacion",
        back_populates="prestacion",
    )
    nomina_detalles = database.relationship("NominaDetalle", back_populates="prestacion")
    prestaciones_acumuladas = database.relationship(
        "PrestacionAcumulada", back_populates="prestacion", cascade="all,delete-orphan"
    )
    cargas_iniciales = database.relationship(
        "CargaInicialPrestacion", back_populates="prestacion", cascade="all,delete-orphan"
    )
    audit_logs = database.relationship(
        "ConceptoAuditLog",
        back_populates="prestacion",
        foreign_keys="ConceptoAuditLog.prestacion_id",
        cascade="all, delete-orphan",
    )


# Definición de componentes de planilla
class PlanillaIngreso(database.Model, BaseTabla):
    __tablename__ = "planilla_ingreso"
    __table_args__ = (database.UniqueConstraint("planilla_id", "percepcion_id", name="uq_planilla_percepcion"),)

    planilla_id = database.Column(database.String(26), database.ForeignKey(FK_PLANILLA_ID), nullable=False)
    percepcion_id = database.Column(database.String(26), database.ForeignKey(FK_PERCEPCION_ID), nullable=False)

    orden = database.Column(database.Integer, nullable=True, default=0)
    editable = database.Column(database.Boolean(), default=True)
    monto_predeterminado = database.Column(database.Numeric(14, 2), nullable=True)
    porcentaje = database.Column(database.Numeric(5, 2), nullable=True)
    activo = database.Column(database.Boolean(), default=True)

    planilla = database.relationship("Planilla", back_populates="planilla_percepciones")
    percepcion = database.relationship("Percepcion", back_populates="planillas")


class PlanillaDeduccion(database.Model, BaseTabla):
    """Association between Planilla and Deduccion with priority ordering.

    The 'prioridad' field determines the order in which deductions are applied.
    This is critical when the net salary doesn't cover all deductions.

    Priority guidelines:
    - 1-100: Legal/mandatory deductions (taxes, social security)
    - 101-200: Court-ordered deductions (alimony, garnishments)
    - 201-300: Company loans and salary advances
    - 301-400: Voluntary deductions (savings, insurance)
    - 401+: Other deductions

    Note: Loan installments from the Adelanto table are handled automatically
    by the payroll engine, not through JSON calculation rules.
    """

    __tablename__ = "planilla_deduccion"
    __table_args__ = (database.UniqueConstraint("planilla_id", "deduccion_id", name="uq_planilla_deduccion"),)

    planilla_id = database.Column(database.String(26), database.ForeignKey(FK_PLANILLA_ID), nullable=False)
    deduccion_id = database.Column(database.String(26), database.ForeignKey(FK_DEDUCCION_ID), nullable=False)

    # Priority order for applying deductions (lower = higher priority)
    prioridad = database.Column(database.Integer, nullable=False, default=100)

    # Legacy field kept for backward compatibility, use 'prioridad' instead
    orden = database.Column(database.Integer, nullable=True, default=0)

    editable = database.Column(database.Boolean(), default=True)
    monto_predeterminado = database.Column(database.Numeric(14, 2), nullable=True)
    porcentaje = database.Column(database.Numeric(5, 2), nullable=True)
    activo = database.Column(database.Boolean(), default=True)

    # Whether this deduction is mandatory (cannot be skipped if salary insufficient)
    es_obligatoria = database.Column(database.Boolean(), default=False)

    # Whether to stop processing if salary is insufficient for this deduction
    detener_si_insuficiente = database.Column(database.Boolean(), default=False)

    planilla = database.relationship("Planilla", back_populates="planilla_deducciones")
    deduccion = database.relationship("Deduccion", back_populates="planillas")


class PlanillaPrestacion(database.Model, BaseTabla):
    __tablename__ = "planilla_prestacion"
    __table_args__ = (database.UniqueConstraint("planilla_id", "prestacion_id", name="uq_planilla_prestacion"),)

    planilla_id = database.Column(database.String(26), database.ForeignKey(FK_PLANILLA_ID), nullable=False)
    prestacion_id = database.Column(database.String(26), database.ForeignKey(FK_PRESTACION_ID), nullable=False)

    orden = database.Column(database.Integer, nullable=True, default=0)
    editable = database.Column(database.Boolean(), default=True)
    monto_predeterminado = database.Column(database.Numeric(14, 2), nullable=True)
    porcentaje = database.Column(database.Numeric(5, 2), nullable=True)
    activo = database.Column(database.Boolean(), default=True)

    planilla = database.relationship("Planilla", back_populates="planilla_prestaciones")
    prestacion = database.relationship("Prestacion", back_populates="planillas")


class PlanillaReglaCalculo(database.Model, BaseTabla):
    """Association between Planilla and ReglaCalculo (calculation rules/tax tables).

    This allows a payroll to have multiple calculation rules associated,
    such as income tax rules, social security rules, etc.
    """

    __tablename__ = "planilla_regla_calculo"
    __table_args__ = (database.UniqueConstraint("planilla_id", "regla_calculo_id", name="uq_planilla_regla"),)

    planilla_id = database.Column(database.String(26), database.ForeignKey(FK_PLANILLA_ID), nullable=False)
    regla_calculo_id = database.Column(database.String(26), database.ForeignKey("regla_calculo.id"), nullable=False)

    # Order of execution (important for dependent calculations)
    orden = database.Column(database.Integer, nullable=False, default=0)

    # Whether this rule is active for this payroll
    activo = database.Column(database.Boolean(), default=True)

    # Optional: override parameters for this specific payroll
    parametros_override = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    planilla = database.relationship("Planilla", back_populates="planilla_reglas_calculo")
    regla_calculo = database.relationship("ReglaCalculo", back_populates="planillas")


class PlanillaEmpleado(database.Model, BaseTabla):
    __tablename__ = "planilla_empleado"
    __table_args__ = (database.UniqueConstraint("planilla_id", "empleado_id", name="uq_planilla_empleado"),)

    planilla_id = database.Column(database.String(26), database.ForeignKey(FK_PLANILLA_ID), nullable=False)
    empleado_id = database.Column(database.String(26), database.ForeignKey(FK_EMPLEADO_ID), nullable=False)

    activo = database.Column(database.Boolean(), default=True)
    fecha_inicio = database.Column(database.Date, nullable=False, default=date.today)
    fecha_fin = database.Column(database.Date, nullable=True)  # si deja de estar en la planilla

    planilla = database.relationship("Planilla", back_populates="planilla_empleados")
    empleado = database.relationship("Empleado", back_populates="planilla_asociaciones")


# Nominas (ejecuciones de planillas)
class Nomina(database.Model, BaseTabla):
    __tablename__ = "nomina"

    planilla_id = database.Column(database.String(26), database.ForeignKey(FK_PLANILLA_ID), nullable=False)
    fecha_generacion = database.Column(database.DateTime, nullable=False, default=utc_now)
    periodo_inicio = database.Column(database.Date, nullable=False)
    periodo_fin = database.Column(database.Date, nullable=False)
    generado_por = database.Column(database.String(150), nullable=True)
    estado = database.Column(
        database.String(30), nullable=False, default=NominaEstado.GENERADO
    )  # calculando, generado, aprobado, aplicado, pagado, anulado, error (all are valid permanent states)

    total_bruto = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    total_deducciones = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    total_neto = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))

    # Progress tracking for background processing
    total_empleados = database.Column(database.Integer, nullable=True, default=0)
    empleados_procesados = database.Column(database.Integer, nullable=True, default=0)
    empleados_con_error = database.Column(database.Integer, nullable=True, default=0)
    errores_calculo = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    procesamiento_en_background = database.Column(database.Boolean, nullable=False, default=False)
    log_procesamiento = database.Column(JSON, nullable=True)  # Stores list of log entries as JSON
    empleado_actual = database.Column(database.String(255), nullable=True)
    job_id_activo = database.Column(database.String(64), nullable=True)
    job_started_at = database.Column(database.DateTime, nullable=True)
    job_completed_at = database.Column(database.DateTime, nullable=True)

    # Audit fields for state changes
    aprobado_por = database.Column(database.String(150), nullable=True)
    aprobado_en = database.Column(database.DateTime, nullable=True)
    aplicado_por = database.Column(database.String(150), nullable=True)
    aplicado_en = database.Column(database.DateTime, nullable=True)
    anulado_por = database.Column(database.String(150), nullable=True)
    anulado_en = database.Column(database.DateTime, nullable=True)
    razon_anulacion = database.Column(database.String(500), nullable=True)

    # Recalculation consistency: Snapshot of calculation context
    # Stores immutable copy of all data needed to reproduce exact same calculation
    fecha_calculo_original = database.Column(database.Date, nullable=True)  # Original calculation date
    configuracion_snapshot = database.Column(JSON, nullable=True)  # Company config at calculation time
    tipos_cambio_snapshot = database.Column(JSON, nullable=True)  # Exchange rates used
    catalogos_snapshot = database.Column(JSON, nullable=True)  # Percepciones/Deducciones/Prestaciones formulas
    es_recalculo = database.Column(database.Boolean, nullable=False, default=False)  # Flag if this is a recalculation
    nomina_original_id = database.Column(database.String(26), nullable=True)  # Reference to original if recalculated

    planilla = database.relationship("Planilla", back_populates="nominas")
    nomina_empleados = database.relationship(
        "NominaEmpleado",
        back_populates="nomina",
    )
    novedades = database.relationship(
        "NominaNovedad",
        back_populates="nomina",
    )
    comprobante_contable = database.relationship(
        "ComprobanteContable",
        back_populates="nomina",
        uselist=False,
    )
    audit_logs = database.relationship(
        "NominaAuditLog",
        back_populates="nomina",
        cascade="all, delete-orphan",
    )
    comparaciones_actual = database.relationship(
        "NominaComparacion",
        back_populates="nomina_actual",
        foreign_keys="NominaComparacion.nomina_actual_id",
    )
    comparaciones_base = database.relationship(
        "NominaComparacion",
        back_populates="nomina_base",
        foreign_keys="NominaComparacion.nomina_base_id",
    )


class NominaComparacion(database.Model, BaseTabla):
    """Cached comparison between two payroll runs in the same planilla."""

    __tablename__ = "nomina_comparacion"
    __table_args__ = (
        database.UniqueConstraint("nomina_base_id", "nomina_actual_id", name="uq_nomina_comparacion_par"),
        database.CheckConstraint("nomina_base_id <> nomina_actual_id", name="ck_nomina_comparacion_distintas"),
    )

    planilla_id = database.Column(database.String(26), database.ForeignKey(FK_PLANILLA_ID), nullable=False)
    nomina_base_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=False)
    nomina_actual_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=False)
    resumen_json = database.Column(JSON, nullable=False)
    base_modificado_en = database.Column(database.DateTime, nullable=True)
    actual_modificado_en = database.Column(database.DateTime, nullable=True)
    es_calculo_actual = database.Column(database.Boolean, nullable=False, default=True)
    planilla_actual_aprobada = database.Column(database.Boolean, nullable=False, default=False)
    generado_en = database.Column(database.DateTime, nullable=False, default=utc_now)

    planilla = database.relationship("Planilla")
    nomina_base = database.relationship("Nomina", foreign_keys=[nomina_base_id], back_populates="comparaciones_base")
    nomina_actual = database.relationship(
        "Nomina",
        foreign_keys=[nomina_actual_id],
        back_populates="comparaciones_actual",
    )


class NominaProgress(database.Model, BaseTabla):
    __tablename__ = "nomina_progress"
    __table_args__ = (database.UniqueConstraint("nomina_id", name="uq_nomina_progress_nomina_id"),)

    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=False)
    job_id = database.Column(database.String(64), nullable=True)
    total_empleados = database.Column(database.Integer, nullable=True, default=0)
    empleados_procesados = database.Column(database.Integer, nullable=True, default=0)
    empleados_con_error = database.Column(database.Integer, nullable=True, default=0)
    errores_calculo = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    log_procesamiento = database.Column(JSON, nullable=True)
    empleado_actual = database.Column(database.String(255), nullable=True)
    actualizado_en = database.Column(database.DateTime, nullable=True)

    nomina = database.relationship("Nomina", backref="progress")


class NominaEmpleado(database.Model, BaseTabla):
    __tablename__ = "nomina_empleado"
    __table_args__ = (database.Index("ix_nomina_empleado_nomina_empleado", "nomina_id", "empleado_id"),)

    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=False)
    empleado_id = database.Column(database.String(26), database.ForeignKey(FK_EMPLEADO_ID), nullable=False)

    salario_bruto = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    total_ingresos = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    total_deducciones = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    salario_neto = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))

    # datos para auditoria/moneda
    moneda_origen_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=True)
    tipo_cambio_aplicado = database.Column(database.Numeric(24, 10), nullable=True)

    nomina = database.relationship("Nomina", back_populates="nomina_empleados")
    empleado = database.relationship("Empleado", back_populates="nominas")

    nomina_detalles = database.relationship(
        "NominaDetalle",
        back_populates="nomina_empleado",
    )

    # Backup de datos del empleado al momento de la generación de la nómina
    cargo_snapshot = database.Column(database.String(150), nullable=True)
    area_snapshot = database.Column(database.String(150), nullable=True)
    centro_costos_snapshot = database.Column(database.String(150), nullable=True)
    sueldo_base_historico = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Tracking de inasistencias (ausencias)
    inasistencia_dias = database.Column(database.Numeric(10, 2), nullable=True, default=Decimal("0.00"))
    inasistencia_horas = database.Column(database.Numeric(10, 2), nullable=True, default=Decimal("0.00"))
    inasistencia_descuento = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))


class NominaDetalle(database.Model, BaseTabla):
    __tablename__ = "nomina_detalle"
    __table_args__ = (database.Index("ix_nomina_detalle_emp_tipo_codigo", "nomina_empleado_id", "tipo", "codigo"),)

    nomina_empleado_id = database.Column(database.String(26), database.ForeignKey("nomina_empleado.id"), nullable=False)
    tipo = database.Column(database.String(15), nullable=False)  # income | deduction | benefit
    codigo = database.Column(database.String(50), nullable=False)
    descripcion = database.Column(database.String(255), nullable=True)
    monto = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    orden = database.Column(database.Integer, nullable=True, default=0)

    # referencias opcionales a catálogo original (si aplica)
    percepcion_id = database.Column(database.String(26), database.ForeignKey(FK_PERCEPCION_ID), nullable=True)
    deduccion_id = database.Column(database.String(26), database.ForeignKey(FK_DEDUCCION_ID), nullable=True)
    prestacion_id = database.Column(database.String(26), database.ForeignKey(FK_PRESTACION_ID), nullable=True)

    nomina_empleado = database.relationship("NominaEmpleado", back_populates="nomina_detalles")
    percepcion = database.relationship("Percepcion", back_populates="nomina_detalles", foreign_keys=[percepcion_id])
    deduccion = database.relationship("Deduccion", back_populates="nomina_detalles", foreign_keys=[deduccion_id])
    prestacion = database.relationship("Prestacion", back_populates="nomina_detalles", foreign_keys=[prestacion_id])


# Liquidaciones (terminaciones laborales)
class LiquidacionConcepto(database.Model, BaseTabla):
    __tablename__ = "liquidacion_concepto"

    codigo = database.Column(database.String(50), unique=True, nullable=False, index=True)
    nombre = database.Column(database.String(150), nullable=False)
    descripcion = database.Column(database.String(255), nullable=True)
    activo = database.Column(database.Boolean(), default=True, nullable=False)


class Liquidacion(database.Model, BaseTabla):
    __tablename__ = "liquidacion"
    __table_args__ = (database.Index("ix_liquidacion_concepto_fk", "concepto_id"),)

    empleado_id = database.Column(database.String(26), database.ForeignKey(FK_EMPLEADO_ID), nullable=False, index=True)
    concepto_id = database.Column(database.String(26), database.ForeignKey("liquidacion_concepto.id"), nullable=True)

    fecha_calculo = database.Column(database.Date, nullable=False, default=date.today)
    ultimo_dia_pagado = database.Column(database.Date, nullable=True)
    dias_por_pagar = database.Column(database.Integer, nullable=False, default=0)

    estado = database.Column(
        database.String(30), nullable=False, default=LiquidacionEstado.BORRADOR
    )  # draft, applied, paid

    total_bruto = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    total_deducciones = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    total_neto = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))

    errores_calculo = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)
    advertencias_calculo = database.Column(JSON, nullable=True, default=list)

    empleado = database.relationship("Empleado")
    concepto = database.relationship("LiquidacionConcepto")
    detalles = database.relationship("LiquidacionDetalle", back_populates="liquidacion", cascade="all,delete-orphan")


class LiquidacionDetalle(database.Model, BaseTabla):
    __tablename__ = "liquidacion_detalle"

    liquidacion_id = database.Column(
        database.String(26), database.ForeignKey("liquidacion.id"), nullable=False, index=True
    )
    tipo = database.Column(database.String(15), nullable=False)  # income | deduction | benefit
    codigo = database.Column(database.String(50), nullable=False)
    descripcion = database.Column(database.String(255), nullable=True)
    monto = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    orden = database.Column(database.Integer, nullable=True, default=0)

    percepcion_id = database.Column(database.String(26), database.ForeignKey(FK_PERCEPCION_ID), nullable=True)
    deduccion_id = database.Column(database.String(26), database.ForeignKey(FK_DEDUCCION_ID), nullable=True)
    prestacion_id = database.Column(database.String(26), database.ForeignKey(FK_PRESTACION_ID), nullable=True)

    liquidacion = database.relationship("Liquidacion", back_populates="detalles")
    percepcion = database.relationship("Percepcion", foreign_keys=[percepcion_id])
    deduccion = database.relationship("Deduccion", foreign_keys=[deduccion_id])
    prestacion = database.relationship("Prestacion", foreign_keys=[prestacion_id])


class NominaNovedad(database.Model, BaseTabla):
    __tablename__ = "nomina_novedad"

    # FK a la ejecución de Nómina (el ID que solicitaste). Can be nullable (None) for floating/pre-assigned novelties.
    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=True)
    # FK al empleado afectado
    empleado_id = database.Column(database.String(26), database.ForeignKey(FK_EMPLEADO_ID), nullable=False)

    tipo_valor = database.Column(database.String(20), nullable=True)  # horas | dias | cantidad | monto | porcentaje

    # El código del concepto que se está modificando/aplicando
    codigo_concepto = database.Column(database.String(50), nullable=False)

    # Valor/cantidad de la novedad (ej. 5 horas, 1500 de comisión, 1 día de ausencia)
    valor_cantidad = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Fecha de ocurrencia del evento (útil para auditoría y prorrateo)
    fecha_novedad = database.Column(database.Date, nullable=True)

    # Referencia opcional al maestro para saber qué regla aplica
    percepcion_id = database.Column(database.String(26), database.ForeignKey(FK_PERCEPCION_ID), nullable=True)
    deduccion_id = database.Column(database.String(26), database.ForeignKey(FK_DEDUCCION_ID), nullable=True)

    # ---- Vacation Module Integration ----
    # Flag to mark this novelty as vacation/time-off
    es_descanso_vacaciones = database.Column(database.Boolean(), default=False, nullable=False)

    # ---- Absence (Inasistencia) Tracking ----
    # Flag to mark this novelty as an absence event
    es_inasistencia = database.Column(database.Boolean(), default=False, nullable=False)
    # Flag to indicate the absence should reduce pay for the day/hour
    descontar_pago_inasistencia = database.Column(database.Boolean(), default=False, nullable=False)

    # Reference to VacationNovelty if this is a vacation leave
    vacation_novelty_id = database.Column(
        database.String(26), database.ForeignKey("vacation_novelty.id"), nullable=True, index=True
    )

    # Dates for vacation period (when es_descanso_vacaciones=True)
    fecha_inicio_descanso = database.Column(database.Date, nullable=True)
    fecha_fin_descanso = database.Column(database.Date, nullable=True)

    # Estado de la novedad: 'pending' | 'executed'
    # Se marca como 'executed' cuando la nómina cambia a estado 'applied'
    estado = database.Column(database.String(20), nullable=False, default="pending")  # Use NovedadEstado enum values

    nomina = database.relationship("Nomina", back_populates="novedades")
    empleado = database.relationship("Empleado", back_populates="novedades_registradas")
    vacation_novelty = database.relationship("VacationNovelty", foreign_keys=[vacation_novelty_id])


# Comprobante Contable (Accounting Voucher)
class ComprobanteContable(database.Model, BaseTabla):
    """Stores the accounting voucher header for audit purposes.

    This model preserves the accounting voucher header generated at the time of payroll
    calculation, preventing configuration changes from affecting historical records.
    Detail lines are stored in ComprobanteContableLinea.

    Audit Trail:
    - aplicado_por: User who applied the nomina (immutable)
    - fecha_aplicacion: Date when nomina was applied (immutable)
    - modificado_por: User who last regenerated the voucher
    - fecha_modificacion: Date when voucher was last regenerated
    """

    __tablename__ = "comprobante_contable"

    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=False, unique=True)

    # Header information
    fecha_calculo = database.Column(database.Date, nullable=False, default=date.today)
    concepto = database.Column(database.String(255), nullable=True)  # Description/concept of the voucher
    moneda_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=True)

    # Summary totals (calculated from lines)
    total_debitos = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    total_creditos = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    balance = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Warnings about incomplete configurations
    advertencias = database.Column(JSON, nullable=True, default=list)

    # Audit trail - immutable fields (set once when nomina is applied)
    aplicado_por = database.Column(database.String(150), nullable=True)
    fecha_aplicacion = database.Column(database.DateTime, nullable=True)

    # Audit trail - modification tracking (updated each time voucher is regenerated)
    modificado_por = database.Column(database.String(150), nullable=True)
    fecha_modificacion = database.Column(database.DateTime, nullable=True)
    veces_modificado = database.Column(database.Integer, nullable=False, default=0)

    nomina = database.relationship("Nomina", back_populates="comprobante_contable")
    moneda = database.relationship("Moneda")
    lineas = database.relationship(
        "ComprobanteContableLinea",
        back_populates="comprobante",
        cascade="all, delete-orphan",
        order_by="ComprobanteContableLinea.orden",
    )


class ComprobanteContableLinea(database.Model, BaseTabla):
    """Stores individual accounting entry lines for each employee's payroll calculation.

    Each line represents a single accounting entry (debit or credit) for a specific
    employee, concept, account, and cost center. Provides complete audit trail.

    Audit Fields:
    - Empleado: empleado_id, empleado_codigo, empleado_nombre
    - Cuenta: codigo_cuenta, descripcion_cuenta
    - Centro de costos: centro_costos
    - Concepto origen: concepto_codigo (código de percepción/deducción/prestación)
    - Tipo: tipo_debito_credito ('debito' o 'credito')
    - Monto: debito o credito (solo uno tiene valor, el otro es 0)
    """

    __tablename__ = "comprobante_contable_linea"

    comprobante_id = database.Column(
        database.String(26), database.ForeignKey("comprobante_contable.id"), nullable=False, index=True
    )
    nomina_empleado_id = database.Column(
        database.String(26), database.ForeignKey("nomina_empleado.id"), nullable=False, index=True
    )

    # Employee information for audit trail (denormalized for easier reporting)
    empleado_id = database.Column(database.String(26), database.ForeignKey(FK_EMPLEADO_ID), nullable=False, index=True)
    empleado_codigo = database.Column(database.String(20), nullable=False, index=True)
    empleado_nombre = database.Column(database.String(255), nullable=False)

    # Accounting account information (nullable to support incomplete configuration)
    codigo_cuenta = database.Column(database.String(64), nullable=True, index=True)
    descripcion_cuenta = database.Column(database.String(255), nullable=True)

    # Cost center for cost allocation
    centro_costos = database.Column(database.String(150), nullable=True, index=True)

    # Amount (only one should be non-zero: debito OR credito)
    tipo_debito_credito = database.Column(database.String(10), nullable=False, index=True)  # 'debito' or 'credito'
    debito = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    credito = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Calculated amount (the actual value, duplicated for convenience)
    monto_calculado = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Source concept information for complete audit trail
    concepto = database.Column(database.String(255), nullable=False)  # Description of the concept
    tipo_concepto = database.Column(
        database.String(20), nullable=False, index=True
    )  # 'salario_base', 'percepcion', 'deduccion', 'prestacion', 'prestamo'
    concepto_codigo = database.Column(database.String(50), nullable=False, index=True)  # Code from source concept

    # Order for consistent display
    orden = database.Column(database.Integer, nullable=False, default=0, index=True)

    comprobante = database.relationship("ComprobanteContable", back_populates="lineas")
    nomina_empleado = database.relationship("NominaEmpleado")
    empleado = database.relationship("Empleado")


# Historial de cambios de salario
class HistorialSalario(database.Model, BaseTabla):
    __tablename__ = "historial_salario"

    empleado_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPLEADO_ID),
        nullable=False,
        index=True,
    )
    fecha_efectiva = database.Column(database.Date, nullable=False, index=True)
    salario_anterior = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    moneda_anterior_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=True)
    salario_nuevo = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    moneda_nueva_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=True)
    motivo = database.Column(database.String(255), nullable=True)
    estado = database.Column(database.String(20), nullable=False, default="draft", index=True)
    autorizado_por = database.Column(database.String(150), nullable=True)
    aprobado_en = database.Column(database.DateTime, nullable=True)
    aplicado_por = database.Column(database.String(150), nullable=True)
    aplicado_en = database.Column(database.DateTime, nullable=True)

    empleado = database.relationship("Empleado", back_populates="historial_salarios")
    moneda_anterior = database.relationship("Moneda", foreign_keys=[moneda_anterior_id])
    moneda_nueva = database.relationship("Moneda", foreign_keys=[moneda_nueva_id])


# Configuración de vacaciones por país/empresa
class ConfiguracionVacaciones(database.Model, BaseTabla):
    __tablename__ = "configuracion_vacaciones"

    codigo = database.Column(database.String(50), unique=True, nullable=False, index=True)
    descripcion = database.Column(database.String(255), nullable=True)
    dias_por_mes = database.Column(database.Numeric(5, 2), nullable=False, default=Decimal("2.50"))
    dias_minimos_descanso = database.Column(database.Integer, nullable=False, default=1)
    dias_maximos_acumulables = database.Column(database.Integer, nullable=True)
    meses_minimos_para_devengar = database.Column(database.Integer, nullable=False, default=1)
    activo = database.Column(database.Boolean(), default=True)

    vacaciones_empleados = database.relationship("VacacionEmpleado", back_populates="configuracion")


# Saldo y control de vacaciones por empleado
class VacacionEmpleado(database.Model, BaseTabla):
    __tablename__ = "vacacion_empleado"
    __table_args__ = (database.UniqueConstraint("empleado_id", "anio", name="uq_vacacion_empleado_anio"),)

    empleado_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPLEADO_ID),
        nullable=False,
        index=True,
    )
    configuracion_id = database.Column(
        database.String(26),
        database.ForeignKey("configuracion_vacaciones.id"),
        nullable=False,
    )
    anio = database.Column(database.Integer, nullable=False)
    dias_devengados = database.Column(database.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    dias_tomados = database.Column(database.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    dias_pendientes = database.Column(database.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    dias_pagados = database.Column(database.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    fecha_ultimo_calculo = database.Column(database.Date, nullable=True)

    empleado = database.relationship("Empleado", back_populates="vacaciones")
    configuracion = database.relationship("ConfiguracionVacaciones", back_populates="vacaciones_empleados")


# Registro de vacaciones descansadas
class VacacionDescansada(database.Model, BaseTabla):
    __tablename__ = "vacacion_descansada"

    empleado_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPLEADO_ID),
        nullable=False,
        index=True,
    )
    fecha_inicio = database.Column(database.Date, nullable=False)
    fecha_fin = database.Column(database.Date, nullable=False)
    dias_tomados = database.Column(database.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    estado = database.Column(database.String(30), nullable=False, default="pending")
    autorizado_por = database.Column(database.String(150), nullable=True)
    fecha_autorizacion = database.Column(database.Date, nullable=True)
    observaciones = database.Column(database.String(500), nullable=True)

    empleado = database.relationship("Empleado", back_populates="vacaciones_descansadas")


# Tabla de impuestos (tramos fiscales)
class TablaImpuesto(database.Model, BaseTabla):
    __tablename__ = "tabla_impuesto"
    __table_args__ = (
        database.UniqueConstraint(
            "deduccion_id",
            "limite_inferior",
            "vigente_desde",
            name="uq_impuesto_tramo_vigencia",
        ),
    )

    deduccion_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_DEDUCCION_ID),
        nullable=False,
        index=True,
    )
    limite_inferior = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    limite_superior = database.Column(database.Numeric(14, 2), nullable=True)
    porcentaje = database.Column(database.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    cuota_fija = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    sobre_excedente_de = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    vigente_desde = database.Column(database.Date, nullable=False)
    vigente_hasta = database.Column(database.Date, nullable=True)
    activo = database.Column(database.Boolean(), default=True)

    deduccion = database.relationship("Deduccion", back_populates="tablas_impuesto")


# Adelantos de salario y préstamos
class Adelanto(database.Model, BaseTabla):
    """Loan and salary advance management.

    Supports both loans (préstamos) with interest rates and salary advances (adelantos).
    Can handle multi-currency loans with automatic conversion tracking.
    """

    __tablename__ = "adelanto"

    empleado_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPLEADO_ID),
        nullable=False,
        index=True,
    )
    deduccion_id = database.Column(database.String(26), database.ForeignKey(FK_DEDUCCION_ID), nullable=True)

    # Tipo: loan o advance
    tipo = database.Column(database.String(20), nullable=False, default="advance")  # advance, loan

    # Fechas
    fecha_solicitud = database.Column(database.Date, nullable=False, default=date.today)
    fecha_aprobacion = database.Column(database.Date, nullable=True)
    fecha_desembolso = database.Column(database.Date, nullable=True)

    # Montos
    monto_solicitado = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    monto_aprobado = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    saldo_pendiente = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Currency support - loan can be in different currency than payroll
    moneda_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=True)
    # Track amounts in both loan currency and payroll currency
    monto_deducido_moneda_planilla = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))
    monto_aplicado_moneda_prestamo = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))

    # Cuotas
    cuotas_pactadas = database.Column(database.Integer, nullable=True)
    monto_por_cuota = database.Column(database.Numeric(14, 2), nullable=True, default=Decimal("0.00"))

    # Interest rates (for loans)
    tasa_interes = database.Column(
        database.Numeric(5, 4), nullable=True, default=Decimal("0.0000")
    )  # e.g., 0.0500 = 5%
    tipo_interes = database.Column(database.String(20), nullable=True, default="none")  # none, simple, compound

    # Amortization method (for loans with interest)
    metodo_amortizacion = database.Column(
        database.String(20), nullable=True, default="french"
    )  # french (constant payment), german (constant amortization)

    # Interest tracking
    interes_acumulado = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )  # Total interest accumulated
    fecha_ultimo_calculo_interes = database.Column(database.Date, nullable=True)  # Last date interest was calculated

    # Accounting fields for initial disbursement
    cuenta_debe = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_debe = database.Column(database.String(255), nullable=True)
    cuenta_haber = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_haber = database.Column(database.String(255), nullable=True)

    # Estado: draft, pending, approved, applied (paid), rejected, cancelled
    estado = database.Column(database.String(30), nullable=False, default=AdelantoEstado.BORRADOR)
    motivo = database.Column(database.String(500), nullable=True)
    aprobado_por = database.Column(database.String(150), nullable=True)
    rechazado_por = database.Column(database.String(150), nullable=True)
    motivo_rechazo = database.Column(database.String(500), nullable=True)

    empleado = database.relationship("Empleado", back_populates="adelantos")
    deduccion = database.relationship("Deduccion", back_populates="adelantos")
    moneda = database.relationship("Moneda")
    abonos = database.relationship("AdelantoAbono", back_populates="adelanto", cascade="all,delete-orphan")
    intereses = database.relationship("InteresAdelanto", back_populates="adelanto", cascade="all,delete-orphan")


# Control de abonos/pagos a adelantos
class AdelantoAbono(database.Model, BaseTabla):
    """Payment record for loans and advances.

    Tracks all payments made against a loan, whether automatic (from payroll)
    or manual (cash, bank transfer, etc.). For manual payments, includes
    comprehensive audit trail information.
    """

    __tablename__ = "adelanto_abono"

    adelanto_id = database.Column(
        database.String(26),
        database.ForeignKey("adelanto.id"),
        nullable=False,
        index=True,
    )
    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=True)
    liquidacion_id = database.Column(database.String(26), database.ForeignKey("liquidacion.id"), nullable=True)
    fecha_abono = database.Column(database.Date, nullable=False, default=date.today)
    monto_abonado = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    saldo_anterior = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    saldo_posterior = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    tipo_abono = database.Column(database.String(30), nullable=False, default="nomina")  # nomina, manual, condonacion
    observaciones = database.Column(database.String(500), nullable=True)

    # Audit trail fields for manual payments
    # These fields ensure compliance and traceability for financial audits
    tipo_comprobante = database.Column(
        database.String(50), nullable=True
    )  # recibo_caja, minuta_deposito, transferencia, cheque, otro
    numero_comprobante = database.Column(database.String(100), nullable=True)  # Receipt/document number
    referencia_bancaria = database.Column(database.String(100), nullable=True)  # Bank reference for electronic payments

    # Accounting entries for manual payments/deductions
    # Optional for payments/forgiveness, but useful for financial reconciliation
    cuenta_debe = database.Column(database.String(64), nullable=True)  # Debit account for payment/deduction
    descripcion_cuenta_debe = database.Column(database.String(255), nullable=True)
    cuenta_haber = database.Column(database.String(64), nullable=True)  # Credit account for payment/deduction
    descripcion_cuenta_haber = database.Column(database.String(255), nullable=True)

    # Loan forgiveness/write-off fields (condonación)
    # Used when company decides not to collect part or all of the loan
    autorizado_por = database.Column(database.String(150), nullable=True)  # Name/title of authorizing person
    documento_soporte = database.Column(
        database.String(50), nullable=True
    )  # Type: correo, memorandum, acta, resolucion, carta, otro
    referencia_documento = database.Column(
        database.String(200), nullable=True
    )  # Document reference (date, number, etc.)
    justificacion = database.Column(database.Text, nullable=True)  # Full justification text for audit trail

    adelanto = database.relationship("Adelanto", back_populates="abonos")
    nomina = database.relationship("Nomina")
    liquidacion = database.relationship("Liquidacion")


# Interest journal for loans
class InteresAdelanto(database.Model, BaseTabla):
    """Interest calculation journal for loans.

    Tracks interest calculations for each loan during payroll processing.
    Each payroll execution calculates interest for the days elapsed since
    the last calculation and records it here.

    This provides a complete audit trail of interest calculations and ensures
    interest is properly tracked and applied to the loan balance.
    """

    __tablename__ = "interes_adelanto"

    adelanto_id = database.Column(
        database.String(26),
        database.ForeignKey("adelanto.id"),
        nullable=False,
        index=True,
    )
    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=True)

    # Calculation period
    fecha_desde = database.Column(database.Date, nullable=False)
    fecha_hasta = database.Column(database.Date, nullable=False)
    dias_transcurridos = database.Column(database.Integer, nullable=False)

    # Interest calculation
    saldo_base = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )  # Balance used for interest calculation
    tasa_aplicada = database.Column(
        database.Numeric(5, 4), nullable=False, default=Decimal("0.0000")
    )  # Interest rate applied
    interes_calculado = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )  # Interest amount calculated

    # Balance tracking
    saldo_anterior = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )  # Balance before interest
    saldo_posterior = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )  # Balance after interest

    observaciones = database.Column(database.String(500), nullable=True)

    adelanto = database.relationship("Adelanto", back_populates="intereses")
    nomina = database.relationship("Nomina")


# Definición de campos personalizados para empleados
class CampoPersonalizado(database.Model, BaseTabla):
    """Custom field definition for employee records.

    Stores the definition of custom fields that can be added to employee records.
    The actual values are stored in the `datos_adicionales` JSON column of Empleado.

    Field types:
    - text: String/text field
    - integer: Integer field
    - decimal: Decimal/float field
    - boolean: Boolean (true/false) field
    """

    __tablename__ = "campo_personalizado"
    __table_args__ = (database.UniqueConstraint("nombre_campo", name="uq_campo_nombre"),)

    nombre_campo = database.Column(database.String(100), unique=True, nullable=False, index=True)
    etiqueta = database.Column(database.String(150), nullable=False)
    tipo_dato = database.Column(database.String(20), nullable=False, default="text")  # text, integer, decimal, boolean
    descripcion = database.Column(database.String(255), nullable=True)
    orden = database.Column(database.Integer, nullable=False, default=0)
    activo = database.Column(database.Boolean(), default=True, nullable=False)


# Reglas de cálculo (impuestos, percepciones, deducciones complejas)
class ReglaCalculo(database.Model, BaseTabla):
    """Calculation rules for taxes, perceptions, and deductions.

    Stores the complete JSON schema for calculating complex rules like
    income tax (IR), social security deductions, etc. The schema defines
    variables, conditions, formulas, and tax lookup tables.

    This allows country-agnostic configuration of tax rules that can be
    versioned and applied based on effective dates.
    """

    __tablename__ = "regla_calculo"
    __table_args__ = (database.UniqueConstraint("codigo", "version", name="uq_regla_codigo_version"),)

    codigo = database.Column(
        database.String(50), nullable=False, index=True
    )  # e.g., 'INCOME_TAX_001', 'SOCIAL_SEC_001'
    nombre = database.Column(database.String(150), nullable=False)
    descripcion = database.Column(database.Text, nullable=True)
    jurisdiccion = database.Column(database.String(100), nullable=True)  # e.g., 'Country A', 'Region B'

    # Reference currency for the tax rule calculations.
    # The rule is currency-agnostic - the actual payroll currency is defined
    # in TipoPlanilla. When the payroll currency differs from the reference
    # currency, exchange rates are applied during calculation.
    # Example: A tax rule may use local currency as reference, but payroll can be in another currency.
    moneda_referencia = database.Column(
        database.String(10), nullable=True
    )  # e.g., 'USD', 'EUR' - reference currency for rule calculations

    version = database.Column(database.String(20), nullable=False, default="1.0.0")  # Semantic versioning

    # Type of rule: 'tax', 'deduction', 'income', 'benefit'
    tipo_regla = database.Column(database.String(30), nullable=False, default="tax")

    # The complete JSON schema defining the calculation logic
    # Structure includes: meta, inputs, steps, tax_tables, output
    esquema_json = database.Column(MutableDict.as_mutable(OrjsonType), nullable=False, default=dict)

    # Validity period
    vigente_desde = database.Column(database.Date, nullable=False)
    vigente_hasta = database.Column(database.Date, nullable=True)

    activo = database.Column(database.Boolean(), default=True, nullable=False)

    # Optional relationship to specific deduction/perception/benefit
    deduccion_id = database.Column(database.String(26), database.ForeignKey(FK_DEDUCCION_ID), nullable=True)
    percepcion_id = database.Column(database.String(26), database.ForeignKey(FK_PERCEPCION_ID), nullable=True)
    prestacion_id = database.Column(database.String(26), database.ForeignKey(FK_PRESTACION_ID), nullable=True)

    # Audit and governance fields
    estado_aprobacion = database.Column(
        database.String(20), nullable=False, default=EstadoAprobacion.BORRADOR, index=True
    )
    aprobado_por = database.Column(database.String(150), nullable=True)
    aprobado_en = database.Column(database.DateTime, nullable=True)
    creado_por_plugin = database.Column(database.Boolean(), default=False, nullable=False)
    plugin_source = database.Column(database.String(200), nullable=True)

    # Relationship to planillas that use this rule
    planillas = database.relationship(
        "PlanillaReglaCalculo",
        back_populates="regla_calculo",
    )
    audit_logs = database.relationship(
        "ReglaCalculoAuditLog",
        back_populates="regla_calculo",
        cascade="all, delete-orphan",
    )


# Acumulados anuales por empleado (para cálculos de impuestos progresivos)
class AcumuladoAnual(database.Model, BaseTabla):
    """Annual accumulated values per employee per payroll type per company.

    Stores running totals of salary, deductions, and taxes for each employee
    per fiscal year, payroll type, and company. This is essential for progressive tax
    calculations which require annual accumulated values.

    IMPORTANT: Accumulated values are tracked per company (empresa_id) to support
    employees who change companies mid-year. Each company maintains separate
    accumulated values since they are distinct legal entities. For tax calculations
    that require total annual income across all employers, the initial accumulated
    values in the Empleado model represent the sum from all previous employers.

    The fiscal year period is defined in the TipoPlanilla (payroll type) to
    support different fiscal periods (not just Jan-Dec).

    Updated after each payroll run to maintain accurate year-to-date totals.
    """

    __tablename__ = "acumulado_anual"
    __table_args__ = (
        database.UniqueConstraint(
            "empleado_id",
            "tipo_planilla_id",
            "empresa_id",
            "periodo_fiscal_inicio",
            name="uq_acumulado_empleado_tipo_empresa_periodo",
        ),
    )

    empleado_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPLEADO_ID),
        nullable=False,
        index=True,
    )

    # Reference to payroll type (which defines the fiscal period)
    tipo_planilla_id = database.Column(
        database.String(26),
        database.ForeignKey("tipo_planilla.id"),
        nullable=False,
        index=True,
    )

    # Company association - critical for employees who change companies
    # Each company tracks accumulated values separately as they are distinct legal entities
    empresa_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPRESA_ID),
        nullable=False,
        index=True,
    )

    # Fiscal period start date (calculated from TipoPlanilla settings)
    # This allows tracking accumulated values per fiscal year
    periodo_fiscal_inicio = database.Column(database.Date, nullable=False, index=True)
    periodo_fiscal_fin = database.Column(database.Date, nullable=False)

    # Accumulated salary values
    salario_bruto_acumulado = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    salario_gravable_acumulado = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Accumulated deductions (before tax)
    deducciones_antes_impuesto_acumulado = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    # Accumulated taxes
    impuesto_retenido_acumulado = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Number of payrolls processed
    periodos_procesados = database.Column(database.Integer, nullable=False, default=0)

    # Last processed period
    ultimo_periodo_procesado = database.Column(database.Date, nullable=True)

    # Monthly accumulated salary (for biweekly/weekly payrolls)
    # This tracks the accumulated salary in the current calendar month
    # Essential for calculations that require month-to-date totals
    salario_acumulado_mes = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    mes_actual = database.Column(database.Integer, nullable=True)  # Current month (1-12) for tracking monthly resets

    # Additional accumulated data (JSON for flexibility)
    # Can store: inss_acumulado, otras_deducciones_acumuladas, percepciones_acumuladas, etc.
    datos_adicionales = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    empleado = database.relationship("Empleado", backref="acumulados_anuales")
    tipo_planilla = database.relationship("TipoPlanilla", back_populates="acumulados")
    empresa = database.relationship("Empresa")

    def reset_mes_acumulado_if_needed(self, periodo_fin: date) -> None:
        """Reset monthly accumulated salary if entering a new month.

        Args:
            periodo_fin: End date of the current payroll period
        """
        if self.mes_actual != periodo_fin.month:
            self.salario_acumulado_mes = Decimal("0.00")
            self.mes_actual = periodo_fin.month


# Global configuration settings
class ConfiguracionGlobal(database.Model, BaseTabla):
    """Global configuration settings for the application.

    Stores system-wide settings like default language, theme preferences, etc.
    Only one record should exist in this table (singleton pattern).
    """

    __tablename__ = "configuracion_global"

    # Language setting: 'en' for English, 'es' for Spanish
    idioma = database.Column(database.String(10), nullable=False, default="en")

    # Additional global settings can be stored as JSON
    configuracion_adicional = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)


# Configuration for calculation parameters
class ConfiguracionCalculos(database.Model, BaseTabla):
    """Configuration table for calculation parameters.

    Stores configurable values for payroll calculations that were previously hardcoded.
    Supports company-specific and country-specific configurations.
    """

    __tablename__ = "config_calculos"
    __table_args__ = (database.UniqueConstraint("empresa_id", "pais_id", name="uq_config_empresa_pais"),)

    # Optional relationships - can be None for global defaults
    empresa_id = database.Column(database.String(26), database.ForeignKey(FK_EMPRESA_ID), nullable=True, index=True)
    pais_id = database.Column(database.String(26), nullable=True, index=True)  # Future: ForeignKey("pais.id")

    # Días base para nómina
    dias_mes_nomina = database.Column(database.Integer, nullable=False, default=30)  # 28, 29, 30, 31
    dias_anio_nomina = database.Column(database.Integer, nullable=False, default=365)  # 360, 365, 366
    horas_jornada_diaria = database.Column(database.Numeric(4, 2), nullable=False, default=Decimal("8.00"))

    # Vacaciones
    dias_mes_vacaciones = database.Column(database.Integer, nullable=False, default=30)
    dias_anio_vacaciones = database.Column(database.Integer, nullable=False, default=365)
    considerar_bisiesto_vacaciones = database.Column(database.Boolean, nullable=False, default=True)

    # Intereses
    dias_anio_financiero = database.Column(
        database.Integer, nullable=False, default=365
    )  # 360 o 365 (default 365 for compatibility)
    meses_anio_financiero = database.Column(database.Integer, nullable=False, default=12)

    # Quincenas
    dias_quincena = database.Column(database.Integer, nullable=False, default=15)  # 14 o 15

    # Liquidaciones
    liquidacion_modo_dias = database.Column(database.String(20), nullable=False, default="calendario")
    liquidacion_factor_calendario = database.Column(database.Integer, nullable=False, default=30)
    liquidacion_factor_laboral = database.Column(database.Integer, nullable=False, default=28)
    liquidacion_prioridad_prestamos = database.Column(database.Integer, nullable=False, default=250)
    liquidacion_prioridad_adelantos = database.Column(database.Integer, nullable=False, default=251)

    # Antigüedad
    dias_mes_antiguedad = database.Column(database.Integer, nullable=False, default=30)
    dias_anio_antiguedad = database.Column(database.Integer, nullable=False, default=365)

    activo = database.Column(database.Boolean, nullable=False, default=True)

    # Relationships
    empresa = database.relationship("Empresa", backref="configuraciones_calculos")


# Prestaciones Acumuladas - Accumulated Benefits Tracking (Transactional)
class PrestacionAcumulada(database.Model, BaseTabla):
    """Transactional log of accumulated employee benefits over time.

    IMPORTANT: This is a transactional (append-only) table for audit purposes.
    Each record represents a single transaction that affects the benefit balance.
    Never update or delete records - always insert new transactions.

    This table maintains a complete audit trail of each benefit (prestacion) for each employee,
    independent of which payroll (planilla) they are assigned to. This is critical because
    employees can change payrolls while their benefit accumulations continue.

    Transaction types:
    - saldo_inicial: Initial balance loading
    - adicion: Addition (increase) - typically from payroll provisions
    - disminucion: Decrease (reduction) - typically from settlements/payments
    - ajuste: Adjustment (can be positive or negative) - manual corrections

    The accumulation respects the tipo_acumulacion setting:
    - monthly: Settled and reset monthly (e.g., INSS, INATEC)
    - annual: Accumulated annually based on payroll configuration
    - lifetime: Accumulated over the employee's entire tenure (e.g., severance)
    """

    __tablename__ = "prestacion_acumulada"
    __table_args__ = (
        database.Index("ix_prestacion_acum_empleado_prestacion", "empleado_id", "prestacion_id"),
        database.Index("ix_prestacion_acum_fecha", "fecha_transaccion"),
        database.Index("ix_prestacion_acum_periodo", "anio", "mes"),
    )

    empleado_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPLEADO_ID),
        nullable=False,
        index=True,
    )
    prestacion_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_PRESTACION_ID),
        nullable=False,
        index=True,
    )

    # Transaction details
    fecha_transaccion = database.Column(database.Date, nullable=False, default=date.today, index=True)
    tipo_transaccion = database.Column(
        database.String(20), nullable=False, index=True
    )  # saldo_inicial | adicion | disminucion | ajuste

    # Period tracking (for reporting and grouping)
    anio = database.Column(database.Integer, nullable=False, index=True)
    mes = database.Column(database.Integer, nullable=False)  # 1-12

    # Currency tracking
    moneda_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=False)

    # Transaction amounts
    # For audit clarity, we store the transaction amount and running balance separately
    monto_transaccion = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )  # Can be positive (addition) or negative (deduction)
    saldo_anterior = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )  # Balance before this transaction
    saldo_nuevo = database.Column(
        database.Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )  # Balance after this transaction

    # Reference to source document that created this transaction
    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=True)
    carga_inicial_id = database.Column(
        database.String(26), database.ForeignKey("carga_inicial_prestacion.id"), nullable=True
    )

    # Company association - for employees who change companies
    # Balances accumulate per company as they are distinct legal entities
    empresa_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPRESA_ID),
        nullable=True,
        index=True,
    )

    # Reversal tracking (if this transaction reverses another)
    transaccion_reversada_id = database.Column(database.String(26), nullable=True)  # FK to another transaction

    # Audit trail
    observaciones = database.Column(database.String(500), nullable=True)
    procesado_por = database.Column(database.String(150), nullable=True)

    # Relationships
    empleado = database.relationship("Empleado")
    prestacion = database.relationship("Prestacion", back_populates="prestaciones_acumuladas")
    moneda = database.relationship("Moneda")
    nomina = database.relationship("Nomina")
    carga_inicial = database.relationship("CargaInicialPrestacion", back_populates="transacciones")
    empresa = database.relationship("Empresa")


# Carga Inicial de Prestaciones - Initial Benefit Balance Loading
class CargaInicialPrestacion(database.Model, BaseTabla):
    """Initial benefit balance loading for system implementation.

    When implementing the system mid-year or mid-employment, this table allows
    loading existing accumulated balances for employees. Once applied, these
    balances are transferred to the PrestacionAcumulada table.

    Workflow:
    1. Create entry in 'draft' status
    2. Review and validate the data
    3. Change status to 'applied'
    4. System automatically creates corresponding PrestacionAcumulada record
    """

    __tablename__ = "carga_inicial_prestacion"
    __table_args__ = (
        database.UniqueConstraint(
            "empleado_id",
            "prestacion_id",
            "anio_corte",
            "mes_corte",
            name="uq_carga_inicial_emp_prest_periodo",
        ),
    )

    empleado_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_EMPLEADO_ID),
        nullable=False,
        index=True,
    )
    prestacion_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_PRESTACION_ID),
        nullable=False,
        index=True,
    )

    # Cutoff period (when this balance was calculated)
    anio_corte = database.Column(database.Integer, nullable=False)
    mes_corte = database.Column(database.Integer, nullable=False)  # 1-12

    # Currency and exchange rate
    moneda_id = database.Column(database.String(26), database.ForeignKey(FK_MONEDA_ID), nullable=False)
    saldo_acumulado = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    tipo_cambio = database.Column(database.Numeric(24, 10), nullable=True, default=Decimal("1.0000000000"))
    saldo_convertido = database.Column(database.Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Status: draft (draft) or applied (applied)
    estado = database.Column(
        database.String(20), nullable=False, default=CargaInicialEstado.BORRADOR
    )  # draft | applied

    # Application tracking
    fecha_aplicacion = database.Column(database.DateTime, nullable=True)
    aplicado_por = database.Column(database.String(150), nullable=True)

    # Notes
    observaciones = database.Column(database.String(500), nullable=True)

    # Relationships
    empleado = database.relationship("Empleado")
    prestacion = database.relationship("Prestacion", back_populates="cargas_iniciales")
    moneda = database.relationship("Moneda")
    transacciones = database.relationship("PrestacionAcumulada", back_populates="carga_inicial")


# ============================================================================
# Vacation Module - Robust, Flexible, Country-Agnostic
# ============================================================================


class VacationPolicy(database.Model, BaseTabla):
    """Vacation policy configuration (payroll/company-specific).

    This model represents the policy engine for vacation management.
    Policies are configurable and define how vacation is accrued, used, and expired.
    Completely agnostic to country-specific laws - all rules are configuration-based.

    Design principles:
    - Policies are declarative, not hardcoded
    - Support for all Americas (LATAM, USA, Canada)
    - Flexible enough to handle diverse legal requirements
    - Associated with Planillas (payrolls) to support multiple countries in consolidated companies
    """

    __tablename__ = "vacation_policy"
    __table_args__ = (
        database.UniqueConstraint("codigo", name="uq_vacation_policy_codigo"),
        database.Index("ix_vacation_policy_empresa", "empresa_id"),
        database.Index("ix_vacation_policy_planilla", "planilla_id"),
    )

    # Policy identification
    codigo = database.Column(database.String(50), unique=True, nullable=False, index=True)
    nombre = database.Column(database.String(200), nullable=False)
    descripcion = database.Column(database.String(500), nullable=True)

    # Payroll association (primary) - policies are tied to specific payrolls
    # This allows different vacation rules for different payrolls in consolidated companies
    planilla_id = database.Column(
        database.String(26),
        database.ForeignKey(FK_PLANILLA_ID, name="fk_vacation_policy_planilla_id"),
        nullable=True,
        index=True,
    )
    planilla = database.relationship("Planilla", foreign_keys=[planilla_id], backref="vacation_policies")

    # Company association (secondary, optional) - for policies that apply to entire company
    empresa_id = database.Column(database.String(26), database.ForeignKey(FK_EMPRESA_ID), nullable=True, index=True)
    empresa = database.relationship("Empresa")

    # Status
    activo = database.Column(database.Boolean(), default=True, nullable=False)

    # ---- Accrual Configuration ----
    # How vacation is earned
    accrual_method = database.Column(
        database.String(20), nullable=False, default=AccrualMethod.PERIODIC
    )  # periodic | proportional | seniority

    # Amount earned per period (for periodic method)
    accrual_rate = database.Column(database.Numeric(10, 4), nullable=False, default=Decimal("0.0000"))

    # Whether to prorate periodic accruals by actual days in the payroll period
    # (False means a full monthly accrual even in shorter months like February).
    prorate_by_period_days = database.Column(database.Boolean(), default=True, nullable=False)

    # How often accrual happens
    accrual_frequency = database.Column(
        database.String(20), nullable=False, default=AccrualFrequency.MONTHLY
    )  # monthly | biweekly | annual

    # Basis for proportional calculation
    accrual_basis = database.Column(
        database.String(20), nullable=True
    )  # days_worked | hours_worked (used when accrual_method=proportional)

    # Minimum service days before accrual begins
    min_service_days = database.Column(database.Integer, nullable=False, default=0)

    # Seniority tiers (JSON format for flexibility)
    # Example: [{"years": 0, "rate": 10}, {"years": 2, "rate": 15}, {"years": 5, "rate": 20}]
    seniority_tiers = database.Column(JSON, nullable=True)

    # ---- Balance Limits ----
    # Maximum balance allowed
    max_balance = database.Column(database.Numeric(10, 4), nullable=True)

    # Maximum that can be carried over to next period
    carryover_limit = database.Column(database.Numeric(10, 4), nullable=True)

    # Allow negative balance (advance vacation)
    allow_negative = database.Column(database.Boolean(), default=False, nullable=False)

    # ---- Expiration Rules ----
    # When does unused vacation expire
    expiration_rule = database.Column(
        database.String(20), nullable=False, default="never"
    )  # never | fiscal_year_end | anniversary | custom_date

    # Months after accrual when vacation expires (used with fiscal_year_end, anniversary)
    expiration_months = database.Column(database.Integer, nullable=True)

    # Custom expiration date (used with custom_date rule)
    expiration_date = database.Column(database.Date, nullable=True)

    # ---- Termination Rules ----
    # Pay out unused vacation on termination
    payout_on_termination = database.Column(database.Boolean(), default=True, nullable=False)

    # ---- Usage Configuration ----
    # Unit type for vacation balances
    unit_type = database.Column(database.String(10), nullable=False, default="days")  # days | hours

    # Count weekends when calculating vacation days
    count_weekends = database.Column(database.Boolean(), default=True, nullable=False)

    # Count holidays when calculating vacation days
    count_holidays = database.Column(database.Boolean(), default=True, nullable=False)

    # Allow partial days/hours
    partial_units_allowed = database.Column(database.Boolean(), default=False, nullable=False)

    # Rounding rule (for partial units): up | down | nearest
    rounding_rule = database.Column(database.String(10), nullable=True, default="nearest")

    # Continue accruing during vacation leave
    accrue_during_leave = database.Column(database.Boolean(), default=True, nullable=False)

    # Whether vacations are paid and should generate a labor liability accounting flow
    son_vacaciones_pagadas = database.Column(database.Boolean(), default=False, nullable=False)

    # Payment rate percentage when vacation is consumed (e.g., 100 means 1 vacation day = 100% of daily salary)
    # Defaults to 100% if not specified. Allows for jurisdictions with different payment rates.
    porcentaje_pago_vacaciones = database.Column(database.Numeric(5, 2), nullable=False, default=Decimal("100.00"))

    # Accounting configuration for paid vacation liability entries
    cuenta_debito_vacaciones_pagadas = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_debito_vacaciones_pagadas = database.Column(database.String(255), nullable=True)
    cuenta_credito_vacaciones_pagadas = database.Column(database.String(64), nullable=True)
    descripcion_cuenta_credito_vacaciones_pagadas = database.Column(database.String(255), nullable=True)

    # Additional configuration (JSON for future extensibility)
    configuracion_adicional = database.Column(JSON, nullable=True)

    # Relationships
    accounts = database.relationship("VacationAccount", back_populates="policy")


class VacationAccount(database.Model, BaseTabla):
    """Vacation account per employee.

    Represents the vacation balance for a single employee under a specific policy.
    This is the control record that tracks current balance and last accrual.

    IMPORTANT: Never update balance directly. All changes must go through VacationLedger.
    """

    __tablename__ = "vacation_account"
    __table_args__ = (
        database.UniqueConstraint("empleado_id", "policy_id", name="uq_vacation_account_emp_policy"),
        database.Index("ix_vacation_account_empleado", "empleado_id"),
        database.Index("ix_vacation_account_policy", "policy_id"),
    )

    # Employee and policy association
    empleado_id = database.Column(database.String(26), database.ForeignKey(FK_EMPLEADO_ID), nullable=False, index=True)
    empleado = database.relationship("Empleado")

    policy_id = database.Column(
        database.String(26), database.ForeignKey("vacation_policy.id"), nullable=False, index=True
    )
    policy = database.relationship("VacationPolicy", back_populates="accounts")

    # Current balance (calculated from ledger)
    current_balance = database.Column(database.Numeric(10, 4), nullable=False, default=Decimal("0.0000"))

    # Last accrual date (for automated accrual processing)
    last_accrual_date = database.Column(database.Date, nullable=True)

    # Status
    activo = database.Column(database.Boolean(), default=True, nullable=False)

    # Relationships
    ledger_entries = database.relationship("VacationLedger", back_populates="account", order_by="VacationLedger.fecha")


class VacationLedger(database.Model, BaseTabla):
    """Immutable ledger of all vacation transactions.

    This is the core of the vacation system - all vacation balance changes are recorded here.
    The ledger is append-only (immutable) for full audit trail.

    Design principle: Balance = SUM(ledger entries)

    Entry types:
    - ACCRUAL: Vacation earned
    - USAGE: Vacation taken
    - ADJUSTMENT: Manual adjustment
    - EXPIRATION: Vacation expired
    - PAYOUT: Vacation paid out (e.g., termination)
    """

    __tablename__ = "vacation_ledger"
    __table_args__ = (
        database.UniqueConstraint(
            "entry_type",
            "source",
            "reference_type",
            "reference_id",
            "account_id",
            name="uq_vacation_ledger_idempotency",
        ),
        database.Index("ix_vacation_ledger_account", "account_id"),
        database.Index("ix_vacation_ledger_fecha", "fecha"),
        database.Index("ix_vacation_ledger_type", "entry_type"),
        database.Index("ix_vacation_ledger_empleado", "empleado_id"),
    )

    # Account reference
    account_id = database.Column(database.String(26), database.ForeignKey("vacation_account.id"), nullable=False)
    account = database.relationship("VacationAccount", back_populates="ledger_entries")

    # Employee reference (for easier querying)
    empleado_id = database.Column(database.String(26), database.ForeignKey(FK_EMPLEADO_ID), nullable=False)
    empleado = database.relationship("Empleado")

    # Transaction details
    fecha = database.Column(database.Date, nullable=False, default=date.today)
    entry_type = database.Column(
        database.String(20), nullable=False
    )  # accrual | usage | adjustment | expiration | payout

    # Quantity (positive for additions, negative for deductions)
    quantity = database.Column(database.Numeric(10, 4), nullable=False)

    # Source of the transaction
    source = database.Column(database.String(50), nullable=False)  # system | novelty | termination | manual

    # Reference to source record (e.g., novelty_id, nomina_id)
    reference_id = database.Column(database.String(26), nullable=True)
    reference_type = database.Column(database.String(50), nullable=True)  # Type of reference (novelty, nomina, etc.)

    # Notes/description
    observaciones = database.Column(database.String(500), nullable=True)

    # Balance after this transaction (for convenience, though can be calculated)
    balance_after = database.Column(database.Numeric(10, 4), nullable=True)


class VacationNovelty(database.Model, BaseTabla):
    """Vacation leave request/novelty.

    Represents a vacation leave request that affects the vacation balance.
    When approved, it creates entries in the VacationLedger.

    This integrates the vacation system with the existing novelty workflow.
    """

    __tablename__ = "vacation_novelty"
    __table_args__ = (
        database.Index("ix_vacation_novelty_empleado", "empleado_id"),
        database.Index("ix_vacation_novelty_account", "account_id"),
        database.Index("ix_vacation_novelty_estado", "estado"),
        database.Index("ix_vacation_novelty_dates", "start_date", "end_date"),
    )

    # Employee and account
    empleado_id = database.Column(database.String(26), database.ForeignKey(FK_EMPLEADO_ID), nullable=False, index=True)
    empleado = database.relationship("Empleado")

    account_id = database.Column(
        database.String(26), database.ForeignKey("vacation_account.id"), nullable=False, index=True
    )
    account = database.relationship("VacationAccount")

    # Leave dates
    start_date = database.Column(database.Date, nullable=False, index=True)
    end_date = database.Column(database.Date, nullable=False, index=True)

    # Units (days or hours, depending on policy)
    units = database.Column(database.Numeric(10, 4), nullable=False)

    # Status
    estado = database.Column(
        database.String(20), nullable=False, default="pending"
    )  # pending | approved | rejected | taken

    # Approval tracking
    fecha_aprobacion = database.Column(database.Date, nullable=True)
    aprobado_por = database.Column(database.String(150), nullable=True)

    # Link to ledger entry (when processed)
    ledger_entry_id = database.Column(database.String(26), database.ForeignKey("vacation_ledger.id"), nullable=True)
    ledger_entry = database.relationship("VacationLedger")

    # Link to payroll novelty (NominaNovedad) when integrated with payroll
    nomina_novedades = database.relationship(
        "NominaNovedad", back_populates="vacation_novelty", foreign_keys="NominaNovedad.vacation_novelty_id"
    )

    # Notes
    observaciones = database.Column(database.String(500), nullable=True)
    motivo_rechazo = database.Column(database.String(500), nullable=True)


# Bridge: Vacation -> Nomina Novedad application
class VacationNominaNovedad(database.Model, BaseTabla):
    """Bridge table between vacation requests and payroll novelties.

    This records when an approved vacation is applied to a specific nomina
    by creating a NominaNovedad entry.
    """

    __tablename__ = "vacation_nomina_novedad"
    __table_args__ = (
        database.UniqueConstraint(
            "vacation_novelty_id",
            "nomina_id",
            name="uq_vacation_nomina_novedad_vacation_nomina",
        ),
        database.Index("ix_vacation_nomina_novedad_vacation", "vacation_novelty_id"),
        database.Index("ix_vacation_nomina_novedad_nomina", "nomina_id"),
        database.Index("ix_vacation_nomina_novedad_novedad", "nomina_novedad_id"),
    )

    vacation_novelty_id = database.Column(
        database.String(26), database.ForeignKey("vacation_novelty.id"), nullable=False
    )
    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=False)
    nomina_novedad_id = database.Column(database.String(26), database.ForeignKey("nomina_novedad.id"), nullable=False)

    aplicado_por = database.Column(database.String(150), nullable=True)
    aplicado_en = database.Column(database.DateTime, nullable=True, default=utc_now)

    vacation_novelty = database.relationship("VacationNovelty")
    nomina = database.relationship("Nomina")
    nomina_novedad = database.relationship("NominaNovedad")


# ============================================================================
# Reports Module
# ============================================================================


class Report(database.Model, BaseTabla):
    """Report definition and configuration.

    Represents both System and Custom reports. System reports are pre-defined
    in the application code with optimized queries. Custom reports are defined
    by users through the UI using a declarative JSON-based configuration.
    """

    __tablename__ = "report"
    __table_args__ = (database.UniqueConstraint("name", name="uq_report_name"),)

    # Basic information
    name = database.Column(database.String(150), nullable=False, unique=True, index=True)
    description = database.Column(database.String(500), nullable=True)

    # Report type: SYSTEM or CUSTOM
    type = database.Column(database.String(20), nullable=False, default="custom")  # system | custom

    # Administrative status
    status = database.Column(database.String(20), nullable=False, default="enabled")  # enabled | disabled

    # Base entity for the report (e.g., Employee, Nomina, Vacation)
    base_entity = database.Column(database.String(100), nullable=False)

    # Report definition (JSON, nullable for System reports as they're coded)
    # For Custom reports: contains columns, filters, sorting, expressions
    definition = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    # System report identifier (for system reports only)
    # Used to identify the report implementation in code
    system_report_id = database.Column(database.String(100), nullable=True, unique=True, index=True)

    # Category for organization (e.g., "payroll", "employee", "vacation")
    category = database.Column(database.String(50), nullable=True, index=True)

    # Relationships
    permissions = database.relationship("ReportRole", back_populates="report", cascade="all,delete-orphan")
    executions = database.relationship("ReportExecution", back_populates="report", cascade="all,delete-orphan")
    audit_entries = database.relationship("ReportAudit", back_populates="report", cascade="all,delete-orphan")


class ReportRole(database.Model, BaseTabla):
    """Report permissions by user role.

    Defines which user types (admin, hhrr, audit) can view, execute, and
    export a specific report.
    """

    __tablename__ = "report_role"
    __table_args__ = (database.UniqueConstraint("report_id", "role", name="uq_report_role"),)

    # Foreign key to report
    report_id = database.Column(database.String(26), database.ForeignKey(FK_REPORT_ID), nullable=False)
    report = database.relationship("Report", back_populates="permissions")

    # User role (admin, hhrr, audit)
    role = database.Column(database.String(20), nullable=False, index=True)

    # Permissions
    can_view = database.Column(database.Boolean(), nullable=False, default=True)
    can_execute = database.Column(database.Boolean(), nullable=False, default=True)
    can_export = database.Column(database.Boolean(), nullable=False, default=False)


class ReportExecution(database.Model, BaseTabla):
    """Report execution history and status.

    Tracks report executions including status, parameters, results,
    and performance metrics. Used for auditing and async execution.
    """

    __tablename__ = "report_execution"

    # Foreign key to report
    report_id = database.Column(database.String(26), database.ForeignKey(FK_REPORT_ID), nullable=False)
    report = database.relationship("Report", back_populates="executions")

    # Execution status
    status = database.Column(
        database.String(20), nullable=False, default="queued"
    )  # queued | running | completed | failed | cancelled

    # Execution parameters (filters applied by user)
    parameters = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    # User who requested the execution
    executed_by = database.Column(database.String(150), nullable=False, index=True)

    # Execution timestamps
    started_at = database.Column(database.DateTime, nullable=True)
    completed_at = database.Column(database.DateTime, nullable=True)

    # Results
    row_count = database.Column(database.Integer, nullable=True)
    execution_time_ms = database.Column(database.Integer, nullable=True)  # in milliseconds

    # Error information (if failed)
    error_message = database.Column(database.String(1000), nullable=True)

    # Export file path (if exported)
    export_file_path = database.Column(database.String(500), nullable=True)
    export_format = database.Column(database.String(20), nullable=True)  # excel, csv, pdf


class ReportAudit(database.Model, BaseTabla):
    """Audit trail for report configuration changes.

    Records all changes to report definitions, status, and permissions
    for compliance and debugging.
    """

    __tablename__ = "report_audit"

    # Foreign key to report
    report_id = database.Column(database.String(26), database.ForeignKey(FK_REPORT_ID), nullable=False)
    report = database.relationship("Report", back_populates="audit_entries")

    # Action performed
    action = database.Column(
        database.String(50), nullable=False, index=True
    )  # created | updated | status_changed | etc

    # User who performed the action
    performed_by = database.Column(database.String(150), nullable=False, index=True)

    # Changes (JSON storing before/after values)
    changes = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    # Timestamp is inherited from BaseTabla


class ConceptoAuditLog(database.Model, BaseTabla):
    """Audit trail for payroll concept changes (percepciones, deducciones, prestaciones).

    Records all changes to payroll concepts including creation, modification, and approval.
    Tracks who made changes, when, and what was changed for governance and compliance.
    """

    __tablename__ = "concepto_audit_log"

    # Foreign keys to the concepts (only one will be set)
    percepcion_id = database.Column(database.String(26), database.ForeignKey(FK_PERCEPCION_ID), nullable=True)
    deduccion_id = database.Column(database.String(26), database.ForeignKey(FK_DEDUCCION_ID), nullable=True)
    prestacion_id = database.Column(database.String(26), database.ForeignKey(FK_PRESTACION_ID), nullable=True)

    # Type of concept (for easier filtering)
    tipo_concepto = database.Column(
        database.String(20), nullable=False, index=True
    )  # percepcion | deduccion | prestacion

    # Action performed
    accion = database.Column(
        database.String(50), nullable=False, index=True
    )  # created | updated | approved | rejected | status_changed

    # User who performed the action
    usuario = database.Column(database.String(150), nullable=False, index=True)

    # Description of the change (human-readable)
    descripcion = database.Column(database.String(1000), nullable=True)

    # Detailed changes (JSON storing field-level before/after values)
    cambios = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    # Previous and new approval status (if applicable)
    estado_anterior = database.Column(database.String(20), nullable=True)
    estado_nuevo = database.Column(database.String(20), nullable=True)

    # Relationships
    percepcion = database.relationship("Percepcion", back_populates="audit_logs")
    deduccion = database.relationship("Deduccion", back_populates="audit_logs")
    prestacion = database.relationship("Prestacion", back_populates="audit_logs")


class PlanillaAuditLog(database.Model, BaseTabla):
    """Audit trail for Planilla changes.

    Records all changes to planillas including creation, modification, approval,
    and configuration changes (adding/removing employees, concepts, etc.).
    """

    __tablename__ = "planilla_audit_log"

    # Foreign key to planilla
    planilla_id = database.Column(database.String(26), database.ForeignKey(FK_PLANILLA_ID), nullable=False)

    # Action performed
    accion = database.Column(
        database.String(50), nullable=False, index=True
    )  # created | updated | approved | rejected | employee_added | employee_removed | concept_added | concept_removed

    # User who performed the action
    usuario = database.Column(database.String(150), nullable=False, index=True)

    # Description of the change (human-readable)
    descripcion = database.Column(database.String(1000), nullable=True)

    # Detailed changes (JSON storing field-level before/after values)
    cambios = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    # Previous and new approval status (if applicable)
    estado_anterior = database.Column(database.String(20), nullable=True)
    estado_nuevo = database.Column(database.String(20), nullable=True)

    # Relationship
    planilla = database.relationship("Planilla", back_populates="audit_logs")


class NominaAuditLog(database.Model, BaseTabla):
    """Audit trail for Nomina state changes.

    Records all state transitions of nominas: generation, approval, application,
    cancellation, and any modifications.
    """

    __tablename__ = "nomina_audit_log"

    # Foreign key to nomina
    nomina_id = database.Column(database.String(26), database.ForeignKey(FK_NOMINA_ID), nullable=False)

    # Action performed
    accion = database.Column(
        database.String(50), nullable=False, index=True
    )  # generated | approved | applied | cancelled | recalculated | modified

    # User who performed the action
    usuario = database.Column(database.String(150), nullable=False, index=True)

    # Description of the change (human-readable)
    descripcion = database.Column(database.String(1000), nullable=True)

    # Detailed changes (JSON storing field-level before/after values)
    cambios = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    # Previous and new state (for state transitions)
    estado_anterior = database.Column(database.String(30), nullable=True)
    estado_nuevo = database.Column(database.String(30), nullable=True)

    # Relationship
    nomina = database.relationship("Nomina", back_populates="audit_logs")


class ReglaCalculoAuditLog(database.Model, BaseTabla):
    """Audit trail for ReglaCalculo changes.

    Records all changes to calculation rules including creation, modification,
    approval, schema changes, and versioning for SOX/COSO compliance.
    """

    __tablename__ = "regla_calculo_audit_log"

    # Foreign key to regla_calculo
    regla_calculo_id = database.Column(database.String(26), database.ForeignKey("regla_calculo.id"), nullable=False)

    # Action performed
    accion = database.Column(
        database.String(50), nullable=False, index=True
    )  # created | updated | approved | rejected | schema_changed | version_changed | status_changed

    # User who performed the action
    usuario = database.Column(database.String(150), nullable=False, index=True)

    # Description of the change (human-readable)
    descripcion = database.Column(database.String(1000), nullable=True)

    # Detailed changes (JSON storing field-level before/after values)
    cambios = database.Column(MutableDict.as_mutable(OrjsonType), nullable=True, default=dict)

    # Previous and new approval status (if applicable)
    estado_anterior = database.Column(database.String(20), nullable=True)
    estado_nuevo = database.Column(database.String(20), nullable=True)

    # Relationship
    regla_calculo = database.relationship("ReglaCalculo", back_populates="audit_logs")
