# Gestión de Empleados

El módulo de empleados es el corazón del sistema de nómina. Aquí se registra toda la información del personal.

## Acceder al Módulo

1. Navegue a **Personal > Empleados**

## Crear Nuevo Empleado

1. Haga clic en **Nuevo Empleado**
2. Complete el formulario con la información del empleado

### Datos Personales

| Campo | Descripción | Requerido |
|-------|-------------|-----------|
| Primer nombre | Primer nombre del empleado | Sí |
| Segundo nombre | Segundo nombre | No |
| Primer apellido | Apellido paterno | Sí |
| Segundo apellido | Apellido materno | No |
| Género | Masculino, Femenino, Otro | No |
| Nacionalidad | País de origen | No |
| Fecha de nacimiento | Fecha de nacimiento | No |
| Tipo de sangre | Grupo sanguíneo | No |

### Identificación

| Campo | Descripción | Requerido |
|-------|-------------|-----------|
| Tipo de identificación | Cédula, Pasaporte, etc. | No |
| Identificación personal | Número de documento | Sí |
| ID Seguridad Social | Número INSS u otro | No |
| ID Fiscal | RUC o número fiscal | No |

### Información Laboral

| Campo | Descripción | Requerido |
|-------|-------------|-----------|
| Fecha de alta | Fecha de ingreso a la empresa | Sí |
| Fecha de baja | Fecha de salida (si aplica) | No |
| Activo | Si el empleado está activo | Sí |
| Cargo | Puesto del empleado | No |
| Área | Departamento o área | No |
| Centro de costos | Centro de costos contable | No |
| Tipo de contrato | Indefinido, temporal, etc. | No |

### Datos de Pago

| Campo | Descripción | Requerido |
|-------|-------------|-----------|
| Salario base | Salario mensual del empleado | Sí |
| Moneda | Moneda del salario | No |
| Banco | Banco donde recibe pago | No |
| Número de cuenta | Cuenta bancaria | No |

### Contacto

| Campo | Descripción | Requerido |
|-------|-------------|-----------|
| Correo electrónico | Email del empleado | No |
| Teléfono | Número de contacto | No |
| Dirección | Dirección de residencia | No |
| Estado civil | Soltero, casado, etc. | No |

### Datos de Implementación

Estos campos se usan cuando el sistema se implementa a mitad de un período fiscal:

| Campo | Descripción |
|-------|-------------|
| Año de implementación inicial | Año fiscal cuando se implementó el sistema |
| Último mes cerrado | Último mes procesado antes del sistema |
| Salario acumulado | Suma de salarios del año antes del sistema |
| Impuesto acumulado | Suma de impuestos pagados antes del sistema |
| Últimos salarios | Salarios de los últimos 3 meses |

!!! info "Implementación a Mitad de Año"
    Si está implementando el sistema a mitad del año fiscal, estos campos permiten que el cálculo del IR considere los valores acumulados previamente.

### Procedimiento Recomendado para Implementación a Mitad de Año Fiscal

Use este flujo cuando la empresa comienza a operar en Coati Payroll después de haber pagado meses previos del mismo año fiscal.

1. Defina en el empleado el **Año de implementación inicial** (ejemplo: `2025`).
2. Registre el **Último mes cerrado** ya pagado fuera del sistema (ejemplo: `7` si julio fue el último mes pagado).
3. Cargue **Salario acumulado** con el total bruto acumulado hasta ese último mes (ejemplo: `70416.67`).
4. Cargue **Impuesto acumulado** con el IR retenido acumulado hasta ese último mes (ejemplo: `1073.67`).
5. Guarde el empleado antes de ejecutar la primera nómina en el sistema.

!!! important "Significado de Impuesto acumulado"
    El campo **Impuesto acumulado** se interpreta como **IR retenido acumulado** del período fiscal, no como deducción antes de impuesto.

!!! note "Comportamiento esperado"
    En la primera nómina posterior al corte (por ejemplo, agosto con último mes cerrado julio), el cálculo usa:

    - Salario bruto acumulado inicial = salario acumulado cargado.
    - IR retenido acumulado inicial = impuesto acumulado cargado.
    - Períodos fiscales procesados iniciales = último mes cerrado (para año fiscal enero-diciembre, julio = 7).

    Estos saldos iniciales se aplican únicamente en el año fiscal configurado de implementación.

## Editar Empleado

1. En la lista de empleados, haga clic en el empleado a editar
2. Modifique los campos necesarios
3. Haga clic en **Guardar**

## Dar de Baja a un Empleado

Para registrar la salida de un empleado:

1. Edite el registro del empleado
2. Complete el campo **Fecha de baja**
3. Desmarque la casilla **Activo**
4. Haga clic en **Guardar**

!!! warning "Empleados Inactivos"
    Los empleados inactivos no se procesan en las nóminas. Asegúrese de desactivarlos después de su fecha de baja.

## Campos Personalizados

El sistema permite agregar campos adicionales a los empleados:

1. Navegue a **Configuración > Campos Personalizados**
2. Cree los campos necesarios
3. Los valores se almacenan en el campo `datos_adicionales` del empleado

### Tipos de Campos

| Tipo | Descripción |
|------|-------------|
| texto | Campo de texto libre |
| entero | Número entero |
| decimal | Número con decimales |
| booleano | Verdadero/Falso |

## Asignar a Planilla

Después de crear un empleado, debe asignarlo a una planilla para que sea procesado en las nóminas:

1. Navegue a **Planillas** y seleccione la planilla
2. En la sección **Empleados**, haga clic en **Agregar Empleado**
3. Seleccione el empleado de la lista
4. Haga clic en **Agregar**

## Historial de Salarios

El sistema mantiene un historial de cambios de salario:

- Cada vez que se modifica el salario base, se registra el cambio
- El historial incluye: fecha efectiva, salario anterior, salario nuevo, motivo

## Ejemplo de Registro

```
Empleado: María López García
├── Identificación: 001-150390-0001A
├── Fecha alta: 15/01/2020
├── Cargo: Contadora
├── Área: Administración
├── Salario base: C$ 25,000.00
├── Moneda: NIO
└── Activo: Sí
```

## Búsqueda de Empleados

Use los filtros disponibles para buscar empleados:

- Por nombre o apellido
- Por número de identificación
- Por estado (activo/inactivo)
- Por área o cargo

## Buenas Prácticas

### Datos Completos

- Complete la mayor cantidad de información posible
- Los datos de identificación son importantes para reportes legales
- La información de contacto facilita la comunicación

### Salarios

- Siempre especifique la moneda del salario
- Documente los cambios de salario con el motivo

### Seguridad Social

- Registre el ID de seguridad social para reportes al INSS
- Registre el ID fiscal para reportes al fisco

## Solución de Problemas

### "Identificación personal duplicada"

- La identificación personal debe ser única
- Verifique si el empleado ya existe en el sistema

### "Empleado no aparece en la planilla"

- Verifique que el empleado esté activo
- Verifique que el empleado esté asignado a la planilla
- Verifique la fecha de inicio de la asignación

## Actualizacion: Implementacion Mid-Year por Empresa

Desde la version 1.7.3, el periodo inicial de implementacion ya no se define en el empleado.

- Se eliminaron los campos de implementacion por empleado:
  - `anio_implementacion_inicial`
  - `mes_ultimo_cierre`
- El empleado mantiene unicamente los saldos de carry-in:
  - `salario_acumulado`
  - `impuesto_acumulado`

Durante el periodo inicial configurado en la empresa, si ambos saldos (`salario_acumulado` e `impuesto_acumulado`) estan en `0` o vacios, el sistema emite advertencia por empleado y continua con el calculo.
