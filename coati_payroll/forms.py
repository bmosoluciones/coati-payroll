# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

"""Forms module.

Contiene los formularios WTForms usados por la aplicación.
"""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
from decimal import Decimal

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional,
    Regexp,
)

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
from coati_payroll.enums import TipoUsuario
from coati_payroll.i18n import _l as _


class LoginForm(FlaskForm):
    """Formulario de inicio de sesión.

    Campos:
    - email: correo o nombre de usuario identificador del usuario
    - password: contraseña
    """

    # Permitimos que el usuario use su nombre de usuario o su correo electrónico
    # para iniciar sesión, por eso no forzamos el validador Email.
    email = StringField(_("Usuario o correo electrónico"), validators=[DataRequired(), Length(max=150)])
    password = PasswordField(_("Contraseña"), validators=[DataRequired(), Length(min=6)])
    submit = SubmitField(_("Entrar"))


# --------------------------------------------------------------------------------------
# CRUD Forms
# --------------------------------------------------------------------------------------


class UserForm(FlaskForm):
    """Form for creating and editing users."""

    usuario = StringField(_("Usuario"), validators=[DataRequired(), Length(max=150)])
    password = PasswordField(_("Contraseña"), validators=[Length(min=6)])
    nombre = StringField(_("Nombre"), validators=[Optional(), Length(max=100)])
    apellido = StringField(_("Apellido"), validators=[Optional(), Length(max=100)])
    correo_electronico = StringField(
        _("Correo electrónico"),
        validators=[Optional(), Email(), Length(max=150)],
    )
    tipo = SelectField(
        _("Tipo de usuario"),
        choices=[
            (TipoUsuario.ADMIN.value, _("Administrador")),
            (TipoUsuario.HHRR.value, _("Recursos Humanos")),
            (TipoUsuario.AUDIT.value, _("Auditoría")),
        ],
        validators=[DataRequired()],
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class ConfiguracionCalculosForm(FlaskForm):
    """Form for editing global calculation configuration parameters."""

    liquidacion_modo_dias = SelectField(
        _("Modo de Días (Liquidación)"),
        choices=[
            ("calendar", _("Calendario")),
            ("working", _("Laboral")),
        ],
        validators=[DataRequired()],
        description=_(
            "Define qué factor se usará como base de días para prorrateos en liquidaciones. "
            "Calendario: usa el Factor Días Calendario (salario_mensual / factor_calendario). "
            "Laboral: usa el Factor Días Laborales (salario_mensual / factor_laboral)."
        ),
    )

    liquidacion_factor_calendario = IntegerField(
        _("Factor Días Calendario (Liquidación)"),
        validators=[DataRequired(), NumberRange(min=1, max=366)],
        default=30,
        description=_("Factor base cuando el modo es Calendario (por defecto 30)."),
    )

    liquidacion_factor_laboral = IntegerField(
        _("Factor Días Laborales (Liquidación)"),
        validators=[DataRequired(), NumberRange(min=1, max=366)],
        default=28,
        description=_("Factor base cuando el modo es Laboral (por defecto 28)."),
    )

    liquidacion_prioridad_prestamos = IntegerField(
        _("Prioridad Préstamos (Liquidación)"),
        validators=[DataRequired(), NumberRange(min=1, max=9999)],
        default=250,
        description=_("Prioridad para aplicar préstamos en liquidaciones (por defecto 250)."),
    )

    liquidacion_prioridad_adelantos = IntegerField(
        _("Prioridad Adelantos (Liquidación)"),
        validators=[DataRequired(), NumberRange(min=1, max=9999)],
        default=251,
        description=_("Prioridad para aplicar adelantos en liquidaciones (por defecto 251)."),
    )

    submit = SubmitField(_("Guardar"))


class ProfileForm(FlaskForm):
    """Form for editing user profile and password."""

    nombre = StringField(_("Nombre"), validators=[Optional(), Length(max=100)])
    apellido = StringField(_("Apellido"), validators=[Optional(), Length(max=100)])
    correo_electronico = StringField(
        _("Correo electrónico"),
        validators=[Optional(), Email(), Length(max=150)],
    )
    current_password = PasswordField(_("Contraseña actual"), validators=[Optional(), Length(min=6)])
    new_password = PasswordField(_("Nueva contraseña"), validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField(_("Confirmar nueva contraseña"), validators=[Optional(), Length(min=6)])
    submit = SubmitField(_("Actualizar Perfil"))


class CurrencyForm(FlaskForm):
    """Form for creating and editing currencies."""

    codigo = StringField(_("Código"), validators=[DataRequired(), Length(max=10)])
    nombre = StringField(_("Nombre"), validators=[DataRequired(), Length(max=100)])
    simbolo = StringField(_("Símbolo"), validators=[Optional(), Length(max=10)])
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class ExchangeRateForm(FlaskForm):
    """Form for creating and editing exchange rates."""

    fecha = DateField(_("Fecha"), validators=[DataRequired()])
    moneda_origen_id = SelectField(_("Moneda origen"), validators=[DataRequired()], coerce=str)
    moneda_destino_id = SelectField(_("Moneda destino"), validators=[DataRequired()], coerce=str)
    tasa = DecimalField(_("Tasa de cambio"), validators=[DataRequired()], places=10)
    submit = SubmitField(_("Guardar"))


class EmployeeForm(FlaskForm):
    """Form for creating and editing employees."""

    codigo_empleado = StringField(
        _("Código de empleado"),
        validators=[
            Optional(),
            Length(max=20),
            Regexp(
                r"^[A-Za-z0-9\-]+$",
                message=_("El código solo puede contener letras, números y guiones."),
            ),
        ],
        description=_("Código único del empleado. Si no se proporciona, se genera automáticamente."),
    )
    primer_nombre = StringField(_("Primer nombre"), validators=[DataRequired(), Length(max=100)])
    segundo_nombre = StringField(_("Segundo nombre"), validators=[Optional(), Length(max=100)])
    primer_apellido = StringField(_("Primer apellido"), validators=[DataRequired(), Length(max=100)])
    segundo_apellido = StringField(_("Segundo apellido"), validators=[Optional(), Length(max=100)])
    genero = SelectField(
        _("Género"),
        choices=[
            ("", _("Seleccionar...")),
            ("male", _("Masculino")),
            ("female", _("Femenino")),
            ("other", _("Otro")),
        ],
        validators=[Optional()],
    )
    nacionalidad = StringField(_("Nacionalidad"), validators=[Optional(), Length(max=100)])
    tipo_identificacion = SelectField(
        _("Tipo de identificación"),
        choices=[
            ("", _("Seleccionar...")),
            ("id_card", _("Cédula")),
            ("passport", _("Pasaporte")),
            ("residence_card", _("Carnet de residente")),
            ("other", _("Otro")),
        ],
        validators=[Optional()],
    )
    identificacion_personal = StringField(_("Identificación personal"), validators=[DataRequired(), Length(max=50)])
    id_seguridad_social = StringField(_("ID Seguridad Social"), validators=[Optional(), Length(max=50)])
    id_fiscal = StringField(_("ID Fiscal"), validators=[Optional(), Length(max=50)])
    tipo_sangre = SelectField(
        _("Tipo de sangre"),
        choices=[
            ("", _("Seleccionar...")),
            ("A+", "A+"),
            ("A-", "A-"),
            ("B+", "B+"),
            ("B-", "B-"),
            ("AB+", "AB+"),
            ("AB-", "AB-"),
            ("O+", "O+"),
            ("O-", "O-"),
        ],
        validators=[Optional()],
    )
    fecha_nacimiento = DateField(_("Fecha de nacimiento"), validators=[Optional()])
    fecha_alta = DateField(_("Fecha de alta"), validators=[DataRequired()])
    fecha_baja = DateField(_("Fecha de baja"), validators=[Optional()])
    activo = BooleanField(_("Activo"), default=True)
    cargo = StringField(_("Cargo"), validators=[Optional(), Length(max=150)])
    area = StringField(_("Área"), validators=[Optional(), Length(max=150)])
    centro_costos = StringField(_("Centro de costos"), validators=[Optional(), Length(max=150)])
    salario_base = DecimalField(_("Salario base"), validators=[DataRequired()], places=2)
    moneda_id = SelectField(_("Moneda"), validators=[Optional()], coerce=str)
    empresa_id = SelectField(_("Empresa"), validators=[Optional()], coerce=str)
    correo = StringField(_("Correo electrónico"), validators=[Optional(), Email(), Length(max=150)])
    telefono = StringField(_("Teléfono"), validators=[Optional(), Length(max=50)])
    direccion = StringField(_("Dirección"), validators=[Optional(), Length(max=255)])
    estado_civil = SelectField(
        _("Estado civil"),
        choices=[
            ("", _("Seleccionar...")),
            ("single", _("Soltero/a")),
            ("married", _("Casado/a")),
            ("divorced", _("Divorciado/a")),
            ("widowed", _("Viudo/a")),
            ("common_law", _("Unión libre")),
        ],
        validators=[Optional()],
    )
    banco = StringField(_("Banco"), validators=[Optional(), Length(max=100)])
    numero_cuenta_bancaria = StringField(_("Número de cuenta bancaria"), validators=[Optional(), Length(max=100)])
    tipo_contrato = SelectField(
        _("Tipo de contrato"),
        choices=[
            ("", _("Seleccionar...")),
            ("permanent", _("Indefinido")),
            ("temporary", _("Temporal")),
            ("project_based", _("Por obra")),
            ("internship", _("Prácticas")),
        ],
        validators=[Optional()],
    )
    # Datos iniciales de implementación
    salario_acumulado = DecimalField(
        _("Salario acumulado"),
        validators=[Optional()],
        places=2,
        description=_("Suma de salarios del año fiscal antes del sistema"),
    )
    impuesto_acumulado = DecimalField(
        _("Impuesto acumulado"),
        validators=[Optional()],
        places=2,
        description=_("Suma de impuestos pagados en el año fiscal antes del sistema"),
    )
    ultimo_salario_1 = DecimalField(
        _("Penúltimo salario mensual"),
        validators=[Optional()],
        places=2,
        description=_("Salario del mes anterior al último"),
    )
    ultimo_salario_2 = DecimalField(
        _("Antepenúltimo salario mensual"),
        validators=[Optional()],
        places=2,
        description=_("Salario de 2 meses antes del último"),
    )
    ultimo_salario_3 = DecimalField(
        _("Tercer salario anterior"),
        validators=[Optional()],
        places=2,
        description=_("Salario de 3 meses antes del último"),
    )
    submit = SubmitField(_("Guardar"))


class SalaryChangeForm(FlaskForm):
    """Form for drafting salary changes before applying them."""

    fecha_efectiva = DateField(_("Fecha efectiva"), validators=[DataRequired()])
    salario_nuevo = DecimalField(
        _("Nuevo salario base"),
        validators=[DataRequired(), NumberRange(min=Decimal("0.01"))],
        places=2,
    )
    moneda_nueva_id = SelectField(_("Nueva moneda"), validators=[Optional()], coerce=str)
    motivo = StringField(_("Motivo"), validators=[Optional(), Length(max=255)])
    submit = SubmitField(_("Guardar borrador"))


class CustomFieldForm(FlaskForm):
    """Form for creating and editing custom employee fields."""

    nombre_campo = StringField(
        _("Nombre del campo"),
        validators=[DataRequired(), Length(max=100)],
        description=_("Nombre interno único del campo (sin espacios ni caracteres especiales)"),
    )
    etiqueta = StringField(
        _("Etiqueta"),
        validators=[DataRequired(), Length(max=150)],
        description=_("Nombre visible del campo en el formulario"),
    )
    tipo_dato = SelectField(
        _("Tipo de dato"),
        choices=[
            ("text", _("Texto")),
            ("integer", _("Número entero")),
            ("decimal", _("Número decimal")),
            ("boolean", _("Verdadero/Falso")),
        ],
        validators=[DataRequired()],
    )
    descripcion = StringField(_("Descripción"), validators=[Optional(), Length(max=255)])
    orden = DecimalField(
        _("Orden de visualización"),
        validators=[Optional()],
        places=0,
        default=0,
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class ReglaCalculoForm(FlaskForm):
    """Form for creating and editing calculation rules."""

    codigo = StringField(
        _("Código"),
        validators=[DataRequired(), Length(max=50)],
        description=_("Código único de la regla (ej: INCOME_TAX_001)"),
    )
    nombre = StringField(
        _("Nombre"),
        validators=[DataRequired(), Length(max=150)],
        description=_("Nombre descriptivo de la regla"),
    )
    descripcion = StringField(
        _("Descripción"),
        validators=[Optional(), Length(max=500)],
    )
    jurisdiccion = StringField(
        _("Jurisdicción"),
        validators=[Optional(), Length(max=100)],
        description=_("País o región donde aplica (ej: Country A)"),
    )
    moneda_referencia = StringField(
        _("Moneda de Referencia"),
        validators=[Optional(), Length(max=10)],
        description=_(
            "Moneda base para cálculos de la regla (ej: NIO). "
            "La moneda de la planilla se define en el Tipo de Planilla."
        ),
    )
    version = StringField(
        _("Versión"),
        validators=[DataRequired(), Length(max=20)],
        default="1.0.0",
        description=_("Versión semántica (ej: 1.0.0)"),
    )
    tipo_regla = SelectField(
        _("Tipo de regla"),
        choices=[
            ("tax", _("Impuesto")),
            ("deduction", _("Deducción")),
            ("income", _("Percepción")),
            ("benefit", _("Prestación")),
        ],
        validators=[DataRequired()],
    )
    vigente_desde = DateField(
        _("Vigente desde"),
        validators=[DataRequired()],
        description=_("Fecha desde la cual la regla es válida"),
    )
    vigente_hasta = DateField(
        _("Vigente hasta"),
        validators=[Optional()],
        description=_("Fecha hasta la cual la regla es válida (vacío = indefinido)"),
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


# ============================================================================
# PAYROLL CONCEPTS FORMS (Percepciones, Deducciones, Prestaciones)
# ============================================================================


class PercepcionForm(FlaskForm):
    """Form for creating and editing perceptions (income items).

    Percepciones are income items that ADD to employee's pay.
    Only Percepciones and Deducciones affect the employee's net salary.
    """

    codigo = StringField(
        _("Código"),
        validators=[DataRequired(), Length(max=50)],
        description=_("Código único de la percepción (ej: SALARIO_BASE)"),
    )
    nombre = StringField(
        _("Nombre"),
        validators=[DataRequired(), Length(max=150)],
        description=_("Nombre descriptivo de la percepción"),
    )
    descripcion = StringField(
        _("Descripción"),
        validators=[Optional(), Length(max=255)],
    )
    formula_tipo = SelectField(
        _("Tipo de Cálculo"),
        choices=[
            ("fixed", _("Monto Fijo")),
            ("salary_percentage", _("Porcentaje del Salario Base")),
            ("gross_percentage", _("Porcentaje del Salario Bruto")),
            ("formula", _("Fórmula Personalizada")),
            ("calculation_rule", _("Regla de Cálculo")),
            ("hours", _("Por Horas")),
            ("days", _("Por Días")),
        ],
        validators=[DataRequired()],
        description=_(
            "Cómo se calcula el monto. "
            "Monto Fijo: usa Monto Predeterminado. "
            "Porcentaje del Salario Base: salario_base × porcentaje. "
            "Porcentaje del Salario Bruto: salario_bruto × porcentaje. "
            "Fórmula Personalizada: usa el esquema de fórmula. "
            "Por Horas/Por Días: toma la novedad del concepto y calcula la tasa según la Base de Cálculo; "
            "el porcentaje actúa como factor sobre la tasa."
        ),
    )
    monto_default = DecimalField(
        _("Monto Predeterminado"),
        validators=[Optional()],
        description=_("Monto fijo cuando aplica"),
    )
    porcentaje = DecimalField(
        _("Porcentaje"),
        validators=[Optional(), NumberRange(min=0, max=100)],
        description=_("Porcentaje para cálculos (0-100)"),
    )
    base_calculo = SelectField(
        _("Base de Cálculo"),
        choices=[
            ("", _("-- Seleccionar --")),
            ("salario_base", _("Salario Base")),
            ("salario_bruto", _("Salario Bruto")),
            ("salario_gravable", _("Salario Gravable")),
            ("salario_neto", _("Salario Neto")),
        ],
        validators=[Optional()],
        description=_(
            "Solo aplica cuando el Tipo de Cálculo es Por Horas o Por Días. "
            "Salario Bruto: la tasa se calcula con salario_bruto. "
            "Cualquier otra opción usa salario_mensual como base."
        ),
    )
    unidad_calculo = SelectField(
        _("Unidad de Cálculo"),
        choices=[
            ("", _("-- Ninguna --")),
            ("hora", _("Por Hora")),
            ("dia", _("Por Día")),
            ("mes", _("Por Mes")),
        ],
        validators=[Optional()],
        description=_("Unidad informativa para reportes/UI; no cambia el cálculo."),
    )
    gravable = BooleanField(
        _("Gravable"),
        default=True,
        description=_("¿Esta percepción está sujeta a impuestos?"),
    )
    recurrente = BooleanField(
        _("Recurrente"),
        default=False,
        description=_("¿Se aplica automáticamente en cada nómina?"),
    )
    # Vigencia
    vigente_desde = DateField(
        _("Vigente Desde"),
        validators=[Optional()],
        description=_("Fecha desde la cual esta percepción es válida"),
    )
    valido_hasta = DateField(
        _("Válido Hasta"),
        validators=[Optional()],
        description=_("Fecha hasta la cual esta percepción es válida (vacío = indefinido)"),
    )
    # Contabilidad
    contabilizable = BooleanField(
        _("Contabilizable"),
        default=True,
    )
    invertir_asiento_contable = BooleanField(
        _("Invertir Asiento Contable"),
        default=False,
        description=_("Invierte la naturaleza contable (debe/haber) para este concepto."),
    )
    codigo_cuenta_debe = StringField(
        _("Cuenta Contable (Debe)"),
        validators=[Optional(), Length(max=64)],
    )
    descripcion_cuenta_debe = StringField(
        _("Descripción Cuenta (Debe)"),
        validators=[Optional(), Length(max=255)],
    )
    codigo_cuenta_haber = StringField(
        _("Cuenta Contable (Haber)"),
        validators=[Optional(), Length(max=64)],
    )
    descripcion_cuenta_haber = StringField(
        _("Descripción Cuenta (Haber)"),
        validators=[Optional(), Length(max=255)],
    )
    mostrar_como_ingreso_reportes = BooleanField(
        _("Mostrar como ingreso en reportes"),
        default=True,
        description=_("Controla si este concepto se muestra como ingreso en reportes."),
    )
    editable_en_nomina = BooleanField(
        _("Editable en Nómina"),
        default=False,
        description=_("¿Permitir modificar el monto durante la nómina?"),
    )
    es_inasistencia = BooleanField(
        _("Es Inasistencia por Defecto"),
        default=False,
        description=_("Si está activo, las novedades de esta percepción se marcarán como inasistencia por defecto."),
    )
    descontar_pago_inasistencia = BooleanField(
        _("Descontar Pago por Inasistencia por Defecto"),
        default=False,
        description=_(
            "Si está activo, las novedades de esta percepción descontarán salario por inasistencia por defecto."
        ),
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class DeduccionForm(FlaskForm):
    """Form for creating and editing deductions."""

    codigo = StringField(
        _("Código"),
        validators=[DataRequired(), Length(max=50)],
        description=_("Código único de la deducción (ej: SOCIAL_SEC_001)"),
    )
    nombre = StringField(
        _("Nombre"),
        validators=[DataRequired(), Length(max=150)],
        description=_("Nombre descriptivo de la deducción"),
    )
    descripcion = StringField(
        _("Descripción"),
        validators=[Optional(), Length(max=255)],
    )
    tipo = SelectField(
        _("Tipo de Deducción"),
        choices=[
            ("general", _("General")),
            ("tax", _("Impuesto")),
            ("social_security", _("Seguro Social")),
            ("loan", _("Préstamo")),
            ("advance", _("Adelanto")),
            ("alimony", _("Pensión Alimenticia")),
            ("savings", _("Ahorro Voluntario")),
            ("union", _("Cuota Sindical")),
            ("other", _("Otro")),
        ],
        validators=[DataRequired()],
        description=_("Clasificación del egreso para reportes y validaciones; no altera el cálculo automático."),
    )
    es_impuesto = BooleanField(
        _("Es Impuesto"),
        default=False,
        description=_("¿Esta deducción es un impuesto (IR, ISR)?"),
    )
    formula_tipo = SelectField(
        _("Tipo de Cálculo"),
        choices=[
            ("fixed", _("Monto Fijo")),
            ("salary_percentage", _("Porcentaje del Salario Base")),
            ("gross_percentage", _("Porcentaje del Salario Bruto")),
            ("porcentaje_gravable", _("Porcentaje del Salario Gravable")),
            ("formula", _("Fórmula Personalizada")),
            ("calculation_rule", _("Regla de Cálculo")),
            ("tabla", _("Tabla de Impuestos")),
        ],
        validators=[DataRequired()],
        description=_(
            "Cómo se calcula el monto. "
            "Monto Fijo: usa Monto Predeterminado. "
            "Porcentaje del Salario Base: salario_base × porcentaje. "
            "Porcentaje del Salario Bruto: salario_bruto × porcentaje. "
            "Fórmula Personalizada: usa el esquema de fórmula. "
            "Porcentaje del Salario Gravable y Tabla de Impuestos requieren una fórmula/regla que lo implemente; "
            "si no hay esquema configurado, no hay cálculo automático."
        ),
    )
    monto_default = DecimalField(
        _("Monto Predeterminado"),
        validators=[Optional()],
        description=_("Monto fijo cuando aplica"),
    )
    porcentaje = DecimalField(
        _("Porcentaje"),
        validators=[Optional(), NumberRange(min=0, max=100)],
        description=_("Porcentaje para cálculos (0-100)"),
    )
    base_calculo = SelectField(
        _("Base de Cálculo"),
        choices=[
            ("", _("-- Seleccionar --")),
            ("salario_base", _("Salario Base")),
            ("salario_bruto", _("Salario Bruto")),
            ("salario_gravable", _("Salario Gravable")),
            ("salario_neto", _("Salario Neto")),
        ],
        validators=[Optional()],
        description=_(
            "Se conserva como referencia para fórmulas. "
            "El motor base solo usa esta base en cálculos por horas/días (no disponibles en deducciones)."
        ),
    )
    unidad_calculo = SelectField(
        _("Unidad de Cálculo"),
        choices=[
            ("", _("-- Ninguna --")),
            ("hora", _("Por Hora")),
            ("dia", _("Por Día")),
            ("mes", _("Por Mes")),
        ],
        validators=[Optional()],
        description=_("Unidad informativa para reportes/UI; no cambia el cálculo."),
    )
    antes_impuesto = BooleanField(
        _("Antes de Impuesto"),
        default=True,
        description=_("¿Se deduce antes de calcular impuestos?"),
    )
    recurrente = BooleanField(
        _("Recurrente"),
        default=False,
        description=_("¿Se aplica automáticamente en cada nómina?"),
    )
    # Vigencia
    vigente_desde = DateField(
        _("Vigente Desde"),
        validators=[Optional()],
        description=_("Fecha desde la cual esta deducción es válida"),
    )
    valido_hasta = DateField(
        _("Válido Hasta"),
        validators=[Optional()],
        description=_("Fecha hasta la cual esta deducción es válida (vacío = indefinido)"),
    )
    # Contabilidad
    contabilizable = BooleanField(
        _("Contabilizable"),
        default=True,
    )
    invertir_asiento_contable = BooleanField(
        _("Invertir Asiento Contable"),
        default=False,
        description=_("Invierte la naturaleza contable (debe/haber) para este concepto."),
    )
    codigo_cuenta_debe = StringField(
        _("Cuenta Contable (Debe)"),
        validators=[Optional(), Length(max=64)],
    )
    descripcion_cuenta_debe = StringField(
        _("Descripción Cuenta (Debe)"),
        validators=[Optional(), Length(max=255)],
    )
    codigo_cuenta_haber = StringField(
        _("Cuenta Contable (Haber)"),
        validators=[Optional(), Length(max=64)],
    )
    descripcion_cuenta_haber = StringField(
        _("Descripción Cuenta (Haber)"),
        validators=[Optional(), Length(max=255)],
    )
    mostrar_como_ingreso_reportes = BooleanField(
        _("Mostrar como ingreso en reportes"),
        default=True,
        description=_("Controla si este concepto se muestra como ingreso en reportes."),
    )
    editable_en_nomina = BooleanField(
        _("Editable en Nómina"),
        default=False,
        description=_("¿Permitir modificar el monto durante la nómina?"),
    )
    es_inasistencia = BooleanField(
        _("Es Inasistencia por Defecto"),
        default=False,
        description=_("Si está activo, las novedades de esta deducción se marcarán como inasistencia por defecto."),
    )
    descontar_pago_inasistencia = BooleanField(
        _("Descontar Pago por Inasistencia por Defecto"),
        default=False,
        description=_(
            "Si está activo, las novedades de esta deducción descontarán salario por inasistencia por defecto."
        ),
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class PlanillaForm(FlaskForm):
    """Form for creating and editing payroll master records (Planilla).

    A Planilla is the central hub that connects employees, perceptions,
    deductions, benefits, and calculation rules.
    """

    nombre = StringField(
        _("Nombre"),
        validators=[DataRequired(), Length(max=150)],
        description=_("Nombre único de la planilla (ej: Planilla Quincenal Córdobas)"),
    )
    descripcion = StringField(
        _("Descripción"),
        validators=[Optional(), Length(max=255)],
    )
    tipo_planilla_id = SelectField(
        _("Tipo de Planilla"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Define periodicidad, período fiscal y configuración de cálculo"),
    )
    moneda_id = SelectField(
        _("Moneda"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Moneda en la que se pagarán los salarios"),
    )
    empresa_id = SelectField(
        _("Empresa"),
        validators=[DataRequired(message=_("La empresa es obligatoria para crear una planilla"))],
        coerce=str,
        description=_("Empresa a la que pertenece esta planilla. Solo empleados de esta empresa podrán ser asignados."),
    )
    mes_inicio_fiscal = SelectField(
        _("Mes Inicio Fiscal"),
        choices=[
            (1, _("Enero")),
            (2, _("Febrero")),
            (3, _("Marzo")),
            (4, _("Abril")),
            (5, _("Mayo")),
            (6, _("Junio")),
            (7, _("Julio")),
            (8, _("Agosto")),
            (9, _("Septiembre")),
            (10, _("Octubre")),
            (11, _("Noviembre")),
            (12, _("Diciembre")),
        ],
        validators=[Optional()],
        coerce=int,
        default=1,
        description=_("Mes en que inicia el a?o fiscal para esta planilla."),
    )
    vacation_policy_id = SelectField(
        _("Regla de Vacaciones"),
        validators=[Optional()],
        coerce=str,
        description=_("Política de vacaciones que esta planilla utilizará para acumulación y descuento."),
    )
    periodo_fiscal_inicio = DateField(
        _("Inicio Período Fiscal"),
        validators=[Optional()],
        description=_("Fecha de inicio del período fiscal actual"),
    )
    periodo_fiscal_fin = DateField(
        _("Fin Período Fiscal"),
        validators=[Optional()],
        description=_("Fecha de fin del período fiscal actual"),
    )
    # Automatic deduction priorities
    prioridad_prestamos = IntegerField(
        _("Prioridad Préstamos"),
        validators=[Optional(), NumberRange(min=1, max=999)],
        default=250,
        description=_("Prioridad para deducir cuotas de préstamos (menor = primero)"),
    )
    prioridad_adelantos = IntegerField(
        _("Prioridad Adelantos"),
        validators=[Optional(), NumberRange(min=1, max=999)],
        default=251,
        description=_("Prioridad para deducir adelantos salariales (menor = primero)"),
    )
    aplicar_prestamos_automatico = BooleanField(
        _("Aplicar Préstamos Automáticamente"),
        default=True,
        description=_("¿Deducir automáticamente las cuotas de préstamos?"),
    )
    aplicar_adelantos_automatico = BooleanField(
        _("Aplicar Adelantos Automáticamente"),
        default=True,
        description=_("¿Deducir automáticamente los adelantos salariales?"),
    )
    # Accounting fields for base salary
    codigo_cuenta_debe_salario = StringField(
        _("Cuenta Débito (Salario Base)"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta de débito para contabilizar el salario base (gasto)"),
    )
    descripcion_cuenta_debe_salario = StringField(
        _("Descripción Cuenta Débito (Salario)"),
        validators=[Optional(), Length(max=255)],
    )
    codigo_cuenta_haber_salario = StringField(
        _("Cuenta Crédito (Salario Base)"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta de crédito para contabilizar el salario base (pasivo)"),
    )
    descripcion_cuenta_haber_salario = StringField(
        _("Descripción Cuenta Crédito (Salario)"),
        validators=[Optional(), Length(max=255)],
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class EmployeeSalaryChangeForm(FlaskForm):
    """Form for salary/currency changes that require historical tracking."""

    fecha_efectiva = DateField(_("Fecha efectiva"), validators=[DataRequired()])
    salario_base = DecimalField(_("Nuevo salario base"), validators=[DataRequired(), NumberRange(min=0)], places=2)
    moneda_id = SelectField(_("Nueva moneda"), validators=[DataRequired()], coerce=str)
    motivo = StringField(_("Motivo"), validators=[Optional(), Length(max=255)])
    submit = SubmitField(_("Autorizar Cambio Salarial"))


class TipoPlanillaForm(FlaskForm):
    """Form for creating and editing payroll types (TipoPlanilla).

    Defines the type of payroll (monthly, biweekly, weekly, etc.) and its
    fiscal period parameters.
    """

    codigo = StringField(
        _("Código"),
        validators=[DataRequired(), Length(max=20)],
        description=_("Código único del tipo de planilla (ej: MENSUAL)"),
    )
    descripcion = StringField(
        _("Descripción"),
        validators=[Optional(), Length(max=150)],
        description=_("Descripción del tipo de planilla"),
    )
    periodicidad = SelectField(
        _("Periodicidad"),
        choices=[
            ("monthly", _("Mensual")),
            ("biweekly", _("Quincenal")),
            ("weekly", _("Semanal")),
        ],
        validators=[DataRequired()],
        description=_(
            "Frecuencia de pago y lógica de prorrateo. "
            "Mensual: si el período cubre el mes completo, paga salario completo; "
            "si no, prorratea por días. "
            "Quincenal: si el período tiene los días configurados, paga salario/quincena; "
            "si no, prorratea por días. "
            "Semanal: siempre prorratea por días."
        ),
    )
    dias = IntegerField(
        _("Días"),
        validators=[DataRequired(), NumberRange(min=1, max=365)],
        default=30,
        description=_("Número de días usados para prorrateos"),
    )
    mes_inicio_fiscal = SelectField(
        _("Mes Inicio Fiscal"),
        choices=[
            ("1", _("Enero")),
            ("2", _("Febrero")),
            ("3", _("Marzo")),
            ("4", _("Abril")),
            ("5", _("Mayo")),
            ("6", _("Junio")),
            ("7", _("Julio")),
            ("8", _("Agosto")),
            ("9", _("Septiembre")),
            ("10", _("Octubre")),
            ("11", _("Noviembre")),
            ("12", _("Diciembre")),
        ],
        validators=[DataRequired()],
        coerce=int,
        default=1,
        description=_(
            "Mes en que inicia el año fiscal. Define el inicio del período fiscal para acumulados "
            "y el cálculo de meses restantes del año."
        ),
    )
    dia_inicio_fiscal = IntegerField(
        _("Día Inicio Fiscal"),
        validators=[DataRequired(), NumberRange(min=1, max=31)],
        default=1,
        description=_("Día del mes en que inicia el año fiscal"),
    )
    acumula_anual = BooleanField(
        _("Acumula Anual"),
        default=True,
        description=_("¿Los valores se acumulan anualmente?"),
    )
    periodos_por_anio = IntegerField(
        _("Períodos por Año"),
        validators=[DataRequired(), NumberRange(min=1, max=365)],
        default=12,
        description=_("Número de períodos de nómina por año fiscal"),
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class PrestacionForm(FlaskForm):
    """Form for creating and editing benefits (employer contributions).

    Prestaciones are employer costs that do NOT affect the employee's net pay.
    Examples: INSS patronal, vacation provisions, aguinaldo provisions.
    """

    codigo = StringField(
        _("Código"),
        validators=[DataRequired(), Length(max=50)],
        description=_("Código único de la prestación (ej: INSS_PATRONAL)"),
    )
    nombre = StringField(
        _("Nombre"),
        validators=[DataRequired(), Length(max=150)],
        description=_("Nombre descriptivo de la prestación"),
    )
    descripcion = StringField(
        _("Descripción"),
        validators=[Optional(), Length(max=255)],
    )
    tipo = SelectField(
        _("Tipo de Prestación"),
        choices=[
            ("employer", _("Aporte Patronal")),
            ("social_security", _("Seguro Social Patronal")),
            ("vacation", _("Vacaciones")),
            ("bonus", _("Aguinaldo / Treceavo Mes")),
            ("severance", _("Indemnización")),
            ("training", _("Capacitación")),
            ("other", _("Otro")),
        ],
        validators=[DataRequired()],
    )
    formula_tipo = SelectField(
        _("Tipo de Cálculo"),
        choices=[
            ("fixed", _("Monto Fijo")),
            ("salary_percentage", _("Porcentaje del Salario Base")),
            ("gross_percentage", _("Porcentaje del Salario Bruto")),
            ("formula", _("Fórmula Personalizada")),
            ("calculation_rule", _("Regla de Cálculo")),
            ("provision", _("Provisión Mensual")),
        ],
        validators=[DataRequired()],
        description=_(
            "Cómo se calcula el monto. "
            "Monto Fijo: usa Monto Predeterminado. "
            "Porcentaje del Salario Base: salario_base × porcentaje. "
            "Porcentaje del Salario Bruto: salario_bruto × porcentaje. "
            "Fórmula Personalizada: usa el esquema de fórmula. "
            "Provisión Mensual requiere una fórmula/regla que lo implemente; "
            "si no hay esquema configurado, no hay cálculo automático."
        ),
    )
    monto_default = DecimalField(
        _("Monto Predeterminado"),
        validators=[Optional()],
        description=_("Monto fijo cuando aplica"),
    )
    porcentaje = DecimalField(
        _("Porcentaje"),
        validators=[Optional(), NumberRange(min=0, max=100)],
        description=_("Porcentaje para cálculos (0-100)"),
    )
    base_calculo = SelectField(
        _("Base de Cálculo"),
        choices=[
            ("", _("-- Seleccionar --")),
            ("salario_base", _("Salario Base")),
            ("salario_bruto", _("Salario Bruto")),
            ("salario_gravable", _("Salario Gravable")),
        ],
        validators=[Optional()],
        description=_(
            "Se conserva como referencia para fórmulas. "
            "El motor base solo usa esta base en cálculos por horas/días (no disponibles en prestaciones)."
        ),
    )
    unidad_calculo = SelectField(
        _("Unidad de Cálculo"),
        choices=[
            ("", _("-- Ninguna --")),
            ("hora", _("Por Hora")),
            ("dia", _("Por Día")),
            ("mes", _("Por Mes")),
        ],
        validators=[Optional()],
        description=_("Unidad informativa para reportes/UI; no cambia el cálculo."),
    )
    tope_aplicacion = DecimalField(
        _("Tope de Aplicación"),
        validators=[Optional()],
        description=_("Monto máximo sobre el cual se aplica el cálculo (ej: techo salarial INSS)"),
    )
    recurrente = BooleanField(
        _("Recurrente"),
        default=True,
        description=_("¿Se provisiona automáticamente en cada nómina?"),
    )
    # Vigencia
    vigente_desde = DateField(
        _("Vigente Desde"),
        validators=[Optional()],
        description=_("Fecha desde la cual esta prestación es válida"),
    )
    valido_hasta = DateField(
        _("Válido Hasta"),
        validators=[Optional()],
        description=_("Fecha hasta la cual esta prestación es válida (vacío = indefinido)"),
    )
    # Contabilidad
    contabilizable = BooleanField(
        _("Contabilizable"),
        default=True,
    )
    codigo_cuenta_debe = StringField(
        _("Cuenta Contable (Debe)"),
        validators=[Optional(), Length(max=64)],
    )
    descripcion_cuenta_debe = StringField(
        _("Descripción Cuenta (Debe)"),
        validators=[Optional(), Length(max=255)],
    )
    codigo_cuenta_haber = StringField(
        _("Cuenta Contable (Haber)"),
        validators=[Optional(), Length(max=64)],
    )
    descripcion_cuenta_haber = StringField(
        _("Descripción Cuenta (Haber)"),
        validators=[Optional(), Length(max=255)],
    )
    editable_en_nomina = BooleanField(
        _("Editable en Nómina"),
        default=False,
        description=_("¿Permitir modificar el monto durante la nómina?"),
    )
    tipo_acumulacion = SelectField(
        _("Tipo de Acumulación"),
        choices=[
            ("monthly", _("Mensual - Liquida cada mes")),
            ("annual", _("Anual - Acumula durante el año")),
            ("lifetime", _("Vida Laboral - Acumula durante toda la relación laboral")),
        ],
        validators=[DataRequired()],
        default="monthly",
        description=_(
            "Define cómo se acumula la prestación. "
            "Mensual: el saldo se reinicia al iniciar un nuevo mes. "
            "Anual: acumula durante el año fiscal. "
            "Vida Laboral: acumula sin reinicio mientras dure la relación laboral."
        ),
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class NominaNovedadForm(FlaskForm):
    """Form for adding novelties (novedades) to a nomina.

    Novedades are adjustments or events that affect an employee's payroll
    for a specific period. They can be associated with:
    - Percepciones (income items like bonuses, overtime)
    - Deducciones (deductions like absences, loans)

    The novedad is linked to a specific employee and a concept (percepcion or deduccion).
    """

    empleado_id = SelectField(
        _("Empleado"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Empleado al que se aplicará la novedad"),
    )
    tipo_concepto = SelectField(
        _("Tipo de Concepto"),
        choices=[
            ("income", _("Percepción (Ingreso)")),
            ("deduction", _("Deducción (Egreso)")),
        ],
        validators=[DataRequired()],
        description=_(
            "Define a qué catálogo se asociará la novedad. "
            "Percepción: requiere seleccionar una percepción y suma al salario. "
            "Deducción: requiere seleccionar una deducción y resta al salario."
        ),
    )
    percepcion_id = SelectField(
        _("Percepción"),
        validators=[Optional()],
        coerce=str,
        description=_("Percepción a la que se asocia la novedad (si aplica)"),
    )
    deduccion_id = SelectField(
        _("Deducción"),
        validators=[Optional()],
        coerce=str,
        description=_("Deducción a la que se asocia la novedad (si aplica)"),
    )
    codigo_concepto = StringField(
        _("Código del Concepto"),
        validators=[DataRequired(), Length(max=50)],
        description=_("Código del concepto que se modifica o aplica"),
    )
    tipo_valor = SelectField(
        _("Tipo de Valor"),
        choices=[
            ("monto", _("Monto Fijo")),
            ("horas", _("Horas")),
            ("dias", _("Días")),
            ("cantidad", _("Cantidad")),
            ("porcentaje", _("Porcentaje")),
        ],
        validators=[DataRequired()],
        description=_(
            "Cómo interpretar el valor registrado. "
            "Monto Fijo: se interpreta como dinero. "
            "Horas/Días: se interpreta como unidades para conceptos por horas/días. "
            "Cantidad: unidades genéricas. "
            "Porcentaje: porcentaje aplicado por la fórmula del concepto. "
            "Nota: el motor suma valor_cantidad por código; debe alinearse con el Tipo de Cálculo del concepto."
        ),
    )
    valor_cantidad = DecimalField(
        _("Valor / Cantidad"),
        validators=[DataRequired()],
        places=2,
        description=_("Valor numérico de la novedad (ej: 5 horas, 1500 de bono)"),
    )
    fecha_novedad = DateField(
        _("Fecha de la Novedad"),
        validators=[Optional()],
        description=_("Fecha en que ocurrió el evento (opcional, para auditoría)"),
    )

    # ---- Absence (Inasistencia) Tracking ----
    es_inasistencia = BooleanField(
        _("Es Inasistencia"),
        default=False,
        description=_("Marcar si esta novedad corresponde a una inasistencia del empleado"),
    )
    descontar_pago_inasistencia = BooleanField(
        _("Descontar Pago por Inasistencia"),
        default=False,
        description=_("Marcar si la inasistencia debe descontar salario por día u hora"),
    )

    # ---- Vacation Module Integration Fields ----
    es_descanso_vacaciones = BooleanField(
        _("Es Descanso de Vacaciones"),
        default=False,
        description=_("Marcar si esta novedad representa vacaciones/descanso del empleado"),
    )
    fecha_inicio_descanso = DateField(
        _("Fecha Inicio Descanso"),
        validators=[Optional()],
        description=_("Fecha de inicio del período de vacaciones (si aplica)"),
    )
    fecha_fin_descanso = DateField(
        _("Fecha Fin Descanso"),
        validators=[Optional()],
        description=_("Fecha de fin del período de vacaciones (si aplica)"),
    )

    submit = SubmitField(_("Guardar"))


class PrestamoForm(FlaskForm):
    """Form for creating and managing loans and salary advances."""

    empleado_id = SelectField(
        _("Empleado"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Seleccione el empleado que solicita el préstamo o adelanto"),
    )
    tipo = SelectField(
        _("Tipo"),
        choices=[
            ("advance", _("Adelanto de Salario")),
            ("loan", _("Préstamo")),
        ],
        validators=[DataRequired()],
        description=_("Adelanto: se descuenta rápidamente; Préstamo: cuotas a largo plazo"),
    )
    fecha_solicitud = DateField(
        _("Fecha de Solicitud"),
        validators=[DataRequired()],
        description=_("Fecha en que se realiza la solicitud"),
    )
    monto_solicitado = DecimalField(
        _("Monto Solicitado"),
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description=_("Monto que solicita el empleado"),
    )
    moneda_id = SelectField(
        _("Moneda"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Moneda del préstamo (puede ser diferente a la de la planilla)"),
    )
    cuotas_pactadas = IntegerField(
        _("Número de Cuotas"),
        validators=[DataRequired(), NumberRange(min=1)],
        description=_("Número de cuotas (nóminas) para pagar el préstamo"),
    )
    tasa_interes = DecimalField(
        _("Tasa de Interés (%)"),
        validators=[Optional(), NumberRange(min=0, max=100)],
        places=4,
        default=0,
        description=_("Tasa de interés anual (ej: 5.0000 para 5%)"),
    )
    tipo_interes = SelectField(
        _("Tipo de Interés"),
        choices=[
            ("none", _("Sin Interés")),
            ("simple", _("Interés Simple")),
            ("compound", _("Interés Compuesto")),
        ],
        validators=[Optional()],
        default="none",
        description=_(
            "Tipo de cálculo de interés. "
            "Sin Interés: no se calcula interés. "
            "Interés Simple: interés proporcional a días sobre el saldo. "
            "Interés Compuesto: capitaliza intereses sobre el saldo."
        ),
    )
    metodo_amortizacion = SelectField(
        _("Método de Amortización"),
        choices=[
            ("french", _("Francés - Cuota Constante")),
            ("german", _("Alemán - Amortización Constante")),
        ],
        validators=[Optional()],
        default="french",
        description=_(
            "Método para calcular las cuotas (solo aplica si hay interés). "
            "Francés: cuota total constante; cambia la proporción capital/interés. "
            "Alemán: amortización de capital constante; cuota total disminuye."
        ),
    )
    cuenta_debe = StringField(
        _("Cuenta Contable Débito"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta contable para el débito del desembolso"),
    )
    cuenta_haber = StringField(
        _("Cuenta Contable Crédito"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta contable para el crédito del desembolso"),
    )
    deduccion_id = SelectField(
        _("Deducción Asociada"),
        validators=[Optional()],
        coerce=str,
        description=_("Deducción para aplicar en nómina (opcional para adelantos)"),
    )
    motivo = StringField(
        _("Motivo"),
        validators=[Optional(), Length(max=500)],
        description=_("Motivo o razón del préstamo"),
    )
    submit = SubmitField(_("Guardar"))


class PrestamoApprovalForm(FlaskForm):
    """Form for approving or rejecting a loan."""

    monto_aprobado = DecimalField(
        _("Monto Aprobado"),
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description=_("Monto aprobado (puede ser diferente al solicitado)"),
    )
    fecha_aprobacion = DateField(
        _("Fecha de Aprobación"),
        validators=[DataRequired()],
        description=_("Fecha de aprobación del préstamo"),
    )
    fecha_desembolso = DateField(
        _("Fecha de Desembolso"),
        validators=[Optional()],
        description=_("Fecha en que se realizó el pago al empleado"),
    )
    monto_por_cuota = DecimalField(
        _("Monto por Cuota"),
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        description=_("Monto a deducir por cada cuota (se calcula automáticamente)"),
    )
    aprobar = SubmitField(_("Aprobar"))
    rechazar = SubmitField(_("Rechazar"))
    motivo_rechazo = StringField(
        _("Motivo de Rechazo"),
        validators=[Optional(), Length(max=500)],
        description=_("Razón del rechazo (requerido si se rechaza)"),
    )


class CondonacionForm(FlaskForm):
    """Form for loan forgiveness/write-off (condonación de deuda)."""

    fecha_condonacion = DateField(
        _("Fecha de Condonación"),
        validators=[DataRequired()],
        description=_("Fecha en que se autoriza la condonación"),
    )
    monto_condonado = DecimalField(
        _("Monto a Condonar"),
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description=_("Monto del saldo que se perdona al empleado"),
    )
    porcentaje_condonado = DecimalField(
        _("Porcentaje a Condonar (%)"),
        validators=[Optional(), NumberRange(min=0, max=100)],
        places=2,
        description=_("Porcentaje del saldo a condonar (opcional, para referencia)"),
    )
    autorizado_por = StringField(
        _("Autorizado Por"),
        validators=[DataRequired(), Length(max=150)],
        description=_("Nombre/cargo de quien autoriza la condonación"),
    )
    documento_soporte = SelectField(
        _("Tipo de Documento Soporte"),
        choices=[
            ("correo", _("Correo Electrónico")),
            ("memorandum", _("Memorándum")),
            ("acta", _("Acta de Junta")),
            ("resolucion", _("Resolución Administrativa")),
            ("carta", _("Carta Formal")),
            ("otro", _("Otro")),
        ],
        validators=[DataRequired()],
        description=_("Tipo de documento que autoriza la condonación"),
    )
    referencia_documento = StringField(
        _("Referencia del Documento"),
        validators=[DataRequired(), Length(max=200)],
        description=_("Número, fecha u otra referencia del documento de autorización"),
    )
    justificacion = StringField(
        _("Justificación Completa"),
        validators=[DataRequired(), Length(min=20, max=1000)],
        description=_("Descripción detallada de la razón y autorización de la condonación"),
    )
    # Optional accounting fields
    cuenta_debe = StringField(
        _("Cuenta Contable Débito"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta contable para el débito (opcional)"),
    )
    cuenta_haber = StringField(
        _("Cuenta Contable Crédito"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta contable para el crédito (opcional)"),
    )
    submit = SubmitField(_("Condonar Deuda"))


class PagoExtraordinarioForm(FlaskForm):
    """Form for recording extraordinary/manual loan payments."""

    fecha_abono = DateField(
        _("Fecha de Pago"),
        validators=[DataRequired()],
        description=_("Fecha en que se realiza el pago extraordinario"),
    )
    monto_abonado = DecimalField(
        _("Monto del Pago"),
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description=_("Monto del pago extraordinario"),
    )
    tipo_aplicacion = SelectField(
        _("Aplicación del Pago"),
        choices=[
            (
                "reducir_cuotas",
                _("Reducir número de cuotas (mantener monto por cuota)"),
            ),
            ("reducir_monto", _("Reducir monto de cuotas (mantener número de cuotas)")),
        ],
        validators=[DataRequired()],
        description=_("Cómo aplicar el pago extraordinario según la ley"),
    )
    # Audit trail fields
    tipo_comprobante = SelectField(
        _("Tipo de Comprobante"),
        choices=[
            ("recibo_caja", _("Recibo Oficial de Caja")),
            ("minuta_deposito", _("Minuta Bancaria de Depósito")),
            ("transferencia", _("Transferencia Bancaria")),
            ("cheque", _("Cheque")),
            ("otro", _("Otro")),
        ],
        validators=[DataRequired()],
        description=_("Tipo de documento que respalda el pago"),
    )
    numero_comprobante = StringField(
        _("Número de Comprobante"),
        validators=[DataRequired(), Length(max=100)],
        description=_("Número de recibo, minuta, transferencia o cheque"),
    )
    referencia_bancaria = StringField(
        _("Referencia Bancaria"),
        validators=[Optional(), Length(max=100)],
        description=_("Número de referencia bancaria o autorización (opcional)"),
    )
    observaciones = StringField(
        _("Observaciones"),
        validators=[Optional(), Length(max=500)],
        description=_("Notas adicionales sobre este pago"),
    )
    # Optional accounting fields
    cuenta_debe = StringField(
        _("Cuenta Contable Débito"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta contable para el débito (opcional)"),
    )
    cuenta_haber = StringField(
        _("Cuenta Contable Crédito"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta contable para el crédito (opcional)"),
    )
    submit = SubmitField(_("Registrar Pago"))


class EmpresaForm(FlaskForm):
    """Form for creating and editing companies/entities."""

    codigo = StringField(
        _("Código"),
        validators=[DataRequired(), Length(max=50)],
        description=_("Código único de la empresa"),
    )
    razon_social = StringField(
        _("Razón Social"),
        validators=[DataRequired(), Length(max=200)],
        description=_("Nombre legal de la empresa"),
    )
    nombre_comercial = StringField(
        _("Nombre Comercial"),
        validators=[Optional(), Length(max=200)],
        description=_("Nombre comercial (opcional)"),
    )
    ruc = StringField(
        _("RUC"),
        validators=[DataRequired(), Length(max=50)],
        description=_("Número de identificación fiscal"),
    )
    direccion = StringField(
        _("Dirección"),
        validators=[Optional(), Length(max=255)],
    )
    telefono = StringField(
        _("Teléfono"),
        validators=[Optional(), Length(max=50)],
    )
    correo = StringField(
        _("Correo Electrónico"),
        validators=[Optional(), Email(), Length(max=150)],
    )
    sitio_web = StringField(
        _("Sitio Web"),
        validators=[Optional(), Length(max=200)],
    )
    representante_legal = StringField(
        _("Representante Legal"),
        validators=[Optional(), Length(max=150)],
    )
    codigo_cuenta_debe_salario = StringField(
        _("Cuenta Débito Salario Básico"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta contable débito para salario básico"),
    )
    descripcion_cuenta_debe_salario = StringField(
        _("Descripción Débito Salario Básico"),
        validators=[Optional(), Length(max=255)],
        description=_("Descripción de la cuenta débito para salario básico"),
    )
    codigo_cuenta_haber_salario = StringField(
        _("Cuenta Crédito Salario Básico"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta contable crédito para salario básico"),
    )
    descripcion_cuenta_haber_salario = StringField(
        _("Descripción Crédito Salario Básico"),
        validators=[Optional(), Length(max=255)],
        description=_("Descripción de la cuenta crédito para salario básico"),
    )
    primer_mes_nomina = SelectField(
        _("Primer Mes de Nómina"),
        choices=[
            ("", _("Seleccionar...")),
            ("1", _("Enero")),
            ("2", _("Febrero")),
            ("3", _("Marzo")),
            ("4", _("Abril")),
            ("5", _("Mayo")),
            ("6", _("Junio")),
            ("7", _("Julio")),
            ("8", _("Agosto")),
            ("9", _("Septiembre")),
            ("10", _("Octubre")),
            ("11", _("Noviembre")),
            ("12", _("Diciembre")),
        ],
        validators=[Optional()],
        coerce=lambda x: int(x) if x else None,
        description=_("Mes del primer período de nómina en el sistema para esta empresa"),
    )
    primer_anio_nomina = IntegerField(
        _("Primer Año de Nómina"),
        validators=[Optional(), NumberRange(min=1900, max=2100)],
        description=_("Año del primer período de nómina en el sistema para esta empresa"),
    )
    activo = BooleanField(_("Activo"), default=True)
    submit = SubmitField(_("Guardar"))


class CargaInicialPrestacionForm(FlaskForm):
    """Form for initial benefit balance loading.

    Used when implementing the system to load existing accumulated balances
    for employees. Supports draft and applied states.
    """

    empleado_id = SelectField(
        _("Empleado"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Seleccione el empleado"),
    )
    prestacion_id = SelectField(
        _("Prestación"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Seleccione la prestación laboral"),
    )
    anio_corte = IntegerField(
        _("Año de Corte"),
        validators=[DataRequired(), NumberRange(min=1900, max=2100)],
        description=_("Año del corte del saldo"),
    )
    mes_corte = SelectField(
        _("Mes de Corte"),
        validators=[DataRequired()],
        coerce=int,
        choices=[
            (1, _("Enero")),
            (2, _("Febrero")),
            (3, _("Marzo")),
            (4, _("Abril")),
            (5, _("Mayo")),
            (6, _("Junio")),
            (7, _("Julio")),
            (8, _("Agosto")),
            (9, _("Septiembre")),
            (10, _("Octubre")),
            (11, _("Noviembre")),
            (12, _("Diciembre")),
        ],
        description=_("Mes del corte del saldo"),
    )
    moneda_id = SelectField(
        _("Moneda"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Moneda del saldo"),
    )
    saldo_acumulado = DecimalField(
        _("Saldo Acumulado"),
        validators=[DataRequired(), NumberRange(min=0)],
        description=_("Saldo acumulado a la fecha de corte"),
    )
    tipo_cambio = DecimalField(
        _("Tipo de Cambio"),
        validators=[Optional(), NumberRange(min=0)],
        default=Decimal("1.0"),
        description=_("Tipo de cambio para conversión (opcional)"),
    )
    saldo_convertido = DecimalField(
        _("Saldo Convertido"),
        validators=[Optional(), NumberRange(min=0)],
        description=_("Saldo convertido con el tipo de cambio propuesto"),
    )
    observaciones = StringField(
        _("Observaciones"),
        validators=[Optional(), Length(max=500)],
        description=_("Notas adicionales sobre esta carga inicial"),
    )
    submit = SubmitField(_("Guardar"))


# ============================================================================
# Vacation Module Forms
# ============================================================================


class VacationPolicyForm(FlaskForm):
    """Form for creating and editing vacation policies."""

    codigo = StringField(
        _("Código"),
        validators=[DataRequired(), Length(max=50)],
        description=_("Código único de la política"),
    )
    nombre = StringField(
        _("Nombre"),
        validators=[DataRequired(), Length(max=200)],
        description=_("Nombre descriptivo de la política"),
    )
    descripcion = StringField(
        _("Descripción"),
        validators=[Optional(), Length(max=500)],
        description=_("Descripción detallada de la política"),
    )
    planilla_id = SelectField(
        _("Planilla (Nómina)"),
        validators=[Optional()],
        coerce=str,
        description=_("Planilla a la que aplica esta política (recomendado para políticas específicas por país)"),
    )
    empresa_id = SelectField(
        _("Empresa"),
        validators=[Optional()],
        coerce=str,
        description=_("Empresa a la que aplica esta política (opcional, para políticas globales)"),
    )
    activo = BooleanField(_("Activo"), default=True)

    # Accrual configuration
    accrual_method = SelectField(
        _("Método de Acumulación"),
        choices=[
            ("periodic", _("Periódico")),
            ("proportional", _("Proporcional")),
            ("seniority", _("Por Antigüedad")),
        ],
        validators=[DataRequired()],
        description=_(
            "Cómo se acumulan las vacaciones. "
            "Periódico: acumula una tasa fija por período. "
            "Proporcional: acumula según días/horas trabajadas. "
            "Por Antigüedad: acumula según tramos de años de servicio."
        ),
    )
    accrual_rate = DecimalField(
        _("Tasa de Acumulación"),
        validators=[Optional(), NumberRange(min=0)],
        default=Decimal("0.0"),
        description=_("Cantidad acumulada por período"),
    )
    accrual_frequency = SelectField(
        _("Frecuencia de Acumulación"),
        choices=[
            ("monthly", _("Mensual")),
            ("biweekly", _("Quincenal")),
            ("annual", _("Anual")),
        ],
        validators=[DataRequired()],
        description=_(
            "Con qué frecuencia se acumula. "
            "Mensual/Quincenal/Anual: define el período esperado para prorrateo "
            "cuando el período real no coincide."
        ),
    )
    prorate_by_period_days = BooleanField(
        _("Prorratear por Días del Período"),
        default=True,
        description=_(
            "Si se desactiva, la acumulación periódica usa la tasa completa del ciclo "
            "(ej: mensual) aunque el mes tenga menos días."
        ),
    )
    accrual_basis = SelectField(
        _("Base de Acumulación"),
        choices=[
            ("", _("N/A")),
            ("days_worked", _("Días Trabajados")),
            ("hours_worked", _("Horas Trabajadas")),
        ],
        validators=[Optional()],
        description=_(
            "Base para cálculo proporcional (solo cuando el método es Proporcional). "
            "Días Trabajados: usa días del período. "
            "Horas Trabajadas: usa horas estándar por día × días del período."
        ),
    )
    min_service_days = IntegerField(
        _("Días Mínimos de Servicio"),
        validators=[Optional(), NumberRange(min=0)],
        default=0,
        description=_("Días de servicio antes de comenzar a acumular"),
    )

    # Balance limits
    max_balance = DecimalField(
        _("Balance Máximo"),
        validators=[Optional(), NumberRange(min=0)],
        description=_("Balance máximo permitido (opcional)"),
    )
    carryover_limit = DecimalField(
        _("Límite de Traspaso"),
        validators=[Optional(), NumberRange(min=0)],
        description=_("Máximo que puede traspasar al siguiente período (opcional)"),
    )
    allow_negative = BooleanField(
        _("Permitir Balance Negativo"),
        default=False,
        description=_("Permitir adelanto de vacaciones"),
    )

    # Expiration rules
    expiration_rule = SelectField(
        _("Regla de Vencimiento"),
        choices=[
            ("never", _("Nunca")),
            ("fiscal_year_end", _("Fin de Año Fiscal")),
            ("anniversary", _("Aniversario")),
            ("custom_date", _("Fecha Personalizada")),
        ],
        validators=[DataRequired()],
        description=_(
            "Cuándo vencen las vacaciones no usadas. "
            "Se guarda como política; no aplica vencimientos automáticos si no hay proceso configurado."
        ),
    )
    expiration_months = IntegerField(
        _("Meses para Vencimiento"),
        validators=[Optional(), NumberRange(min=0)],
        description=_("Meses después del acumulación antes de vencer (opcional)"),
    )
    expiration_date = DateField(
        _("Fecha de Vencimiento"),
        validators=[Optional()],
        description=_("Fecha personalizada de vencimiento (opcional)"),
    )

    # Termination rules
    payout_on_termination = BooleanField(
        _("Pagar al Terminar"),
        default=True,
        description=_("Pagar vacaciones no usadas al terminar relación laboral"),
    )

    # Usage configuration
    unit_type = SelectField(
        _("Tipo de Unidad"),
        choices=[
            ("days", _("Días")),
            ("hours", _("Horas")),
        ],
        validators=[DataRequired()],
        description=_("Unidad para medir saldos y solicitudes; se muestra en reportes y formularios."),
    )
    count_weekends = BooleanField(
        _("Contar Fines de Semana"),
        default=True,
        description=_("Incluir fines de semana al calcular días de vacaciones"),
    )
    count_holidays = BooleanField(
        _("Contar Feriados"),
        default=True,
        description=_("Incluir feriados al calcular días de vacaciones"),
    )
    partial_units_allowed = BooleanField(
        _("Permitir Unidades Parciales"),
        default=False,
        description=_("Permitir fracciones de días/horas"),
    )
    rounding_rule = SelectField(
        _("Regla de Redondeo"),
        choices=[
            ("nearest", _("Más Cercano")),
            ("up", _("Hacia Arriba")),
            ("down", _("Hacia Abajo")),
        ],
        validators=[Optional()],
        description=_(
            "Cómo redondear unidades parciales. "
            "Se guarda como política; requiere un proceso que aplique el redondeo."
        ),
    )
    accrue_during_leave = BooleanField(
        _("Acumular Durante Vacaciones"),
        default=True,
        description=_("Continuar acumulando durante período de vacaciones"),
    )

    son_vacaciones_pagadas = BooleanField(
        _("Son vacaciones pagadas"),
        default=False,
        description=_(
            "Si está activo, la acumulación/consumo de vacaciones genera contabilización de pasivo laboral en la nómina"
        ),
    )
    porcentaje_pago_vacaciones = DecimalField(
        _("Porcentaje de pago de vacaciones"),
        validators=[Optional(), NumberRange(min=0, max=999.99)],
        default=Decimal("100.00"),
        description=_(
            "Porcentaje del salario diario a pagar por día de vacaciones (ej: 100 = pago completo, 50 = medio día)"
        ),
    )
    cuenta_debito_vacaciones_pagadas = StringField(
        _("Cuenta débito vacaciones pagadas"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta de gasto (débito) para registrar el devengo de vacaciones pagadas"),
    )
    descripcion_cuenta_debito_vacaciones_pagadas = StringField(
        _("Descripción cuenta débito vacaciones pagadas"),
        validators=[Optional(), Length(max=255)],
        description=_("Descripción de la cuenta débito para vacaciones pagadas"),
    )
    cuenta_credito_vacaciones_pagadas = StringField(
        _("Cuenta crédito vacaciones pagadas"),
        validators=[Optional(), Length(max=64)],
        description=_("Cuenta de pasivo (crédito) para registrar el devengo de vacaciones pagadas"),
    )
    descripcion_cuenta_credito_vacaciones_pagadas = StringField(
        _("Descripción cuenta crédito vacaciones pagadas"),
        validators=[Optional(), Length(max=255)],
        description=_("Descripción de la cuenta crédito para vacaciones pagadas"),
    )

    submit = SubmitField(_("Guardar"))


class VacationAccountForm(FlaskForm):
    """Form for creating vacation accounts."""

    empleado_id = SelectField(
        _("Empleado"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Empleado al que pertenece esta cuenta"),
    )
    policy_id = SelectField(
        _("Política de Vacaciones"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Política que rige esta cuenta"),
    )
    current_balance = DecimalField(
        _("Balance Inicial"),
        validators=[DataRequired(), NumberRange(min=0)],
        default=Decimal("0.0"),
        description=_("Balance inicial de vacaciones"),
    )
    activo = BooleanField(_("Activo"), default=True)

    submit = SubmitField(_("Guardar"))


class VacationLeaveRequestForm(FlaskForm):
    """Form for creating vacation leave requests."""

    empleado_id = SelectField(
        _("Empleado"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Empleado que solicita las vacaciones"),
    )
    start_date = DateField(
        _("Fecha de Inicio"),
        validators=[DataRequired()],
        description=_("Primer día de vacaciones (inicio del período de descanso)"),
    )
    end_date = DateField(
        _("Fecha de Fin"),
        validators=[DataRequired()],
        description=_("Último día de vacaciones (fin del período de descanso)"),
    )
    units = DecimalField(
        _("Días/Horas de Vacaciones a Descontar"),
        validators=[DataRequired(), NumberRange(min=0)],
        description=_("IMPORTANTE: Días u horas reales a descontar del saldo acumulado de vacaciones."),
    )
    observaciones = StringField(
        _("Observaciones"),
        validators=[Optional(), Length(max=500)],
        description=_("Notas adicionales sobre la solicitud"),
    )

    submit = SubmitField(_("Solicitar"))


class VacationTakenForm(FlaskForm):
    """Form for registering vacation days actually taken (with automatic novelty creation).

    This form is used to register vacation time that has been taken by an employee,
    automatically creating the vacation record and the associated novelty (NominaNovedad).

    IMPORTANT:
    - The 'dias_descontados' field represents the actual vacation days to deduct
      from the employee's balance, which may differ from the calendar days in the date range
      based on company policy (e.g., taking Friday+Monday = 4 calendar days but only 2 vacation days).
    - The novelty MUST be associated with a Percepcion or Deduccion for payroll calculations.
    """

    empleado_id = SelectField(
        _("Empleado"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Empleado que tomó las vacaciones"),
    )
    fecha_inicio = DateField(
        _("Fecha Inicio del Descanso"),
        validators=[DataRequired()],
        description=_("Primer día del período de descanso (calendario)"),
    )
    fecha_fin = DateField(
        _("Fecha Fin del Descanso"),
        validators=[DataRequired()],
        description=_("Último día del período de descanso (calendario)"),
    )
    dias_descontados = DecimalField(
        _("Días/Horas a Descontar del Saldo"),
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description=_("CRÍTICO: Días u horas reales a descontar según política (ej: viernes+lunes = 2 días, no 4)"),
    )

    # Asociación con Percepción o Deducción (REQUERIDO)
    tipo_concepto = SelectField(
        _("Tipo de Concepto"),
        choices=[
            ("deduction", _("Deducción (Descuento)")),
            ("income", _("Percepción (Pago de Vacaciones)")),
        ],
        validators=[DataRequired()],
        description=_(
            "Define si las vacaciones generan un descuento o un pago. "
            "Deducción: requiere seleccionar una deducción. "
            "Percepción: requiere seleccionar una percepción."
        ),
    )
    percepcion_id = SelectField(
        _("Percepción"),
        validators=[Optional()],
        coerce=str,
        description=_("Percepción asociada (si tipo_concepto es percepcion)"),
    )
    deduccion_id = SelectField(
        _("Deducción"),
        validators=[Optional()],
        coerce=str,
        description=_("Deducción asociada (si tipo_concepto es deduccion)"),
    )

    observaciones = StringField(
        _("Observaciones"),
        validators=[Optional(), Length(max=500)],
        description=_("Notas adicionales"),
    )

    submit = SubmitField(_("Registrar Vacaciones"))


class VacationInitialBalanceForm(FlaskForm):
    """Form for loading initial vacation balance for an employee.

    Used during system implementation to set the initial accumulated vacation
    balance for employees who already have vacation time earned before the
    system goes live.

    Creates an ADJUSTMENT ledger entry with the initial balance.
    """

    empleado_id = SelectField(
        _("Empleado"),
        validators=[DataRequired()],
        coerce=str,
        description=_("Empleado para cargar saldo inicial"),
    )
    saldo_inicial = DecimalField(
        _("Saldo Inicial de Vacaciones"),
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        description=_("Días u horas de vacaciones acumuladas al momento de implementación"),
    )
    fecha_corte = DateField(
        _("Fecha de Corte"),
        validators=[DataRequired()],
        description=_("Fecha a la que corresponde el saldo inicial (típicamente fecha de implementación del sistema)"),
    )
    observaciones = StringField(
        _("Observaciones"),
        validators=[Optional(), Length(max=500)],
        description=_("Notas sobre el origen del saldo inicial"),
    )

    submit = SubmitField(_("Cargar Saldo Inicial"))


class ConfiguracionIdiomaForm(FlaskForm):
    idioma = SelectField(_("Idioma"), validators=[DataRequired()])
    submit = SubmitField(_("Guardar Cambios"))
