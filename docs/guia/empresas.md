# Gestión de Empresas

La gestión de empresas permite que el sistema maneje nóminas para múltiples entidades o razones sociales desde una sola instalación. Esta funcionalidad es especialmente útil cuando un departamento de Recursos Humanos administra varias empresas o entidades dentro del mismo grupo corporativo.

## Conceptos Clave

### ¿Qué es una Empresa?

Una **empresa** o **entidad** es una razón social independiente que tiene sus propios empleados y planillas. En Coati Payroll, cada empresa representa una entidad legal separada con:

- Su propia razón social y RUC (Registro Único de Contribuyente)
- Empleados asociados específicamente a ella
- Planillas independientes para procesar su nómina

### ¿Cuándo usar Empresas?

El sistema de empresas es **opcional**. Use esta funcionalidad cuando:

✅ **Sí, necesita empresas cuando:**

- Gestiona nóminas para múltiples razones sociales
- Su departamento de RRHH atiende varias empresas del mismo grupo
- Necesita separar empleados y planillas por entidad legal

❌ **No necesita empresas cuando:**

- Solo gestiona una empresa
- Prefiere una configuración más simple
- Puede dejar este campo vacío en empleados y planillas

!!! info "Funcionamiento Opcional"
    Si no configura empresas, el sistema funciona perfectamente para una sola entidad. Los campos de empresa en empleados y planillas son opcionales.

## Separación de Datos

### Empleados y Planillas

- **Empleados** se asocian a una empresa específica
- **Planillas** se asocian a una empresa específica
- Solo se pueden asignar empleados de la misma empresa a una planilla

### Conceptos Compartidos

Los siguientes elementos son **independientes** de las empresas y pueden compartirse:

- **Percepciones**: Un mismo concepto de bono puede usarse en varias empresas
- **Deducciones**: El INSS o IR se configuran una vez para todas las empresas
- **Prestaciones**: Las prestaciones patronales son comunes a todas las empresas

!!! tip "Ventaja del Diseño"
    Este diseño permite configurar una vez los conceptos de nómina (percepciones, deducciones, prestaciones) y reutilizarlos en todas las empresas que gestione.

## Crear una Empresa

### Paso 1: Acceder al Módulo

1. En el menú lateral, vaya a **Configuración**
2. Seleccione **Empresas**
3. Haga clic en el botón **Nueva Empresa**

### Paso 2: Información Básica

Complete los datos de identificación de la empresa:

| Campo | Descripción | Requerido |
|-------|-------------|-----------|
| **Código** | Código único interno (ej: `EMP001`) | ✅ Sí |
| **Razón Social** | Nombre legal completo de la empresa | ✅ Sí |
| **Nombre Comercial** | Nombre comercial si difiere de la razón social | ❌ No |
| **RUC** | Registro Único de Contribuyente | ✅ Sí |

!!! warning "Datos Únicos"
    El **Código** y el **RUC** deben ser únicos en el sistema.

### Paso 3: Datos de Contacto

Opcionalmente, agregue información de contacto:

- **Dirección**: Dirección física de la empresa
- **Teléfono**: Número de contacto principal
- **Correo Electrónico**: Email de contacto
- **Sitio Web**: URL del sitio web corporativo

### Paso 4: Representante Legal

- **Representante Legal**: Nombre del representante legal de la empresa

### Paso 5: Guardar

1. Verifique que todos los datos sean correctos
2. Haga clic en **Guardar**
3. La empresa quedará activa y disponible para asignar empleados y planillas

## Configuración Contable de Salario Básico en Empresa

Desde la versión **1.7.4**, la empresa puede definir las cuentas contables del salario básico que usa el comprobante resumido de nómina:

- **Cuenta Débito Salario Básico**
- **Descripción Débito Salario Básico**
- **Cuenta Crédito Salario Básico**
- **Descripción Crédito Salario Básico**

### ¿Por qué configurarlo en Empresa?

- Permite una fuente de verdad única para varias planillas de la misma razón social.
- Reduce inconsistencias cuando diferentes planillas comparten la misma política contable.
- Mantiene compatibilidad con planillas legacy (fallback), pero se recomienda centralizar en empresa.

## Asignar Empresas

### Asignar Empleados a una Empresa

Al crear o editar un empleado:

1. Vaya a **Empleados** > **Nuevo Empleado** (o edite uno existente)
2. En la sección de información laboral, encontrará el campo **Empresa**
3. Seleccione la empresa correspondiente del desplegable
4. Guarde los cambios

!!! note "Empleados sin Empresa"
    Un empleado puede no tener empresa asignada. Esto es útil durante la transición o para empleados que no requieren esta clasificación.

### Asignar Planillas a una Empresa

Al crear o editar una planilla:

1. Vaya a **Planillas** > **Nueva Planilla** (o edite una existente)
2. En la configuración básica, encontrará el campo **Empresa**
3. Seleccione la empresa correspondiente
4. Guarde los cambios

!!! warning "Importante: Validación de Empresa"
    Al asignar empleados a una planilla, el sistema verifica que el empleado y la planilla pertenezcan a la misma empresa. No podrá asignar empleados de una empresa diferente a la planilla.

## Validaciones del Sistema

El sistema implementa las siguientes reglas de negocio:

### ✅ Permitido

- Crear empleados sin empresa asignada
- Crear planillas sin empresa asignada
- Asignar empleados **sin empresa** a cualquier planilla
- Asignar empleados de la **misma empresa** que la planilla

### ❌ No Permitido

- Asignar empleados de una empresa **diferente** a la planilla
- Eliminar una empresa que tiene empleados asignados
- Eliminar una empresa que tiene planillas asignadas

!!! example "Ejemplo de Validación"
    **Escenario:**
    
    - Empresa A tiene empleado Juan
    - Empresa B tiene planilla de nómina mensual
    
    **Resultado:** No se puede asignar a Juan (Empresa A) a la planilla de Empresa B.
    
    **Solución:** Cambiar la empresa de Juan a Empresa B, o crear una planilla para Empresa A.

## Editar una Empresa

1. Vaya a **Configuración** > **Empresas**
2. Busque la empresa en la lista
3. Haga clic en el icono de edición (lápiz)
4. Realice los cambios necesarios
5. Haga clic en **Guardar**

## Activar/Desactivar una Empresa

Para desactivar temporalmente una empresa sin eliminarla:

1. Vaya a **Configuración** > **Empresas**
2. Busque la empresa en la lista
3. Haga clic en el botón de activar/desactivar (toggle)
4. La empresa se marcará como inactiva y no aparecerá en los selectores

!!! tip "Desactivación vs Eliminación"
    Es recomendable **desactivar** en lugar de **eliminar** para mantener el historial.

## Eliminar una Empresa

!!! danger "Precaución"
    Solo se pueden eliminar empresas que **no** tengan empleados ni planillas asignadas.

Para eliminar una empresa:

1. Asegúrese de que no tiene empleados ni planillas asociadas
2. Vaya a **Configuración** > **Empresas**
3. Busque la empresa en la lista
4. Haga clic en el icono de eliminar (basura)
5. Confirme la eliminación

## Casos de Uso Comunes

### Caso 1: Grupo Empresarial

**Situación:** Una holding con 3 empresas subsidiarias.

**Configuración:**

1. Crear 3 empresas (Subsidiaria A, B y C)
2. Asignar empleados a cada subsidiaria
3. Crear planillas específicas para cada subsidiaria
4. Configurar las percepciones, deducciones y prestaciones una sola vez (se comparten)

**Beneficio:** Un solo sistema gestiona todas las empresas con datos separados legalmente.

### Caso 2: Transición Gradual

**Situación:** Empresa que adquiere otra y quiere migrar gradualmente.

**Configuración:**

1. Crear empresa nueva en el sistema
2. Migrar empleados gradualmente cambiando su empresa asignada
3. Las planillas antiguas siguen operando
4. Crear planillas nuevas para la empresa adquirida

**Beneficio:** Transición controlada sin interrumpir operaciones.

### Caso 3: Separación por División

**Situación:** Misma empresa con divisiones que requieren reportes separados.

**Configuración:**

1. Crear una empresa por división (usando el mismo RUC pero códigos diferentes)
2. O usar el campo `area` o `centro_costos` en lugar de empresas

**Recomendación:** Si no necesita separación legal, use áreas o centros de costo en lugar de empresas.

## Mejores Prácticas

### ✅ Hacer

- Definir empresas desde el inicio si gestiona múltiples entidades
- Usar códigos consistentes y fáciles de identificar (EMP001, EMP002)
- Desactivar empresas obsoletas en lugar de eliminarlas
- Validar que RUC y razón social sean correctos antes de guardar

### ❌ Evitar

- Crear empresas innecesarias para separaciones que no son legales
- Cambiar empresa de empleados frecuentemente (causa problemas en historial)
- Eliminar empresas con historial de nóminas
- Usar empresas para separar áreas o departamentos internos

## Reportes y Consultas

Aunque los reportes específicos por empresa están fuera del alcance de esta guía, el sistema permite:

- Filtrar empleados por empresa
- Filtrar planillas por empresa
- Los cálculos de nómina respetan la empresa asignada
- El historial de nóminas mantiene la trazabilidad por empresa

## Preguntas Frecuentes

### ¿Es obligatorio crear empresas?

No. El sistema funciona perfectamente sin empresas para casos de una sola entidad.

### ¿Puedo tener empleados sin empresa?

Sí. Los empleados sin empresa pueden asignarse a cualquier planilla.

### ¿Las deducciones son por empresa?

No. Deducciones, percepciones y prestaciones son compartidas entre todas las empresas.

### ¿Puedo cambiar la empresa de un empleado?

Sí, pero tenga cuidado con el historial de nóminas ya procesadas.

### ¿Cómo afecta a las nóminas existentes?

Las nóminas ya generadas mantienen los datos históricos de la empresa al momento de ejecución.

## Siguiente Paso

Después de configurar empresas, continúe con:

- [Gestión de Empleados](empleados.md)
- [Configuración de Planillas](planillas.md)
- [Tutorial: Nómina Completa](../tutorial/nomina-completa.md)

## Implementacion de Nomina por Empresa

Cada empresa define su primer periodo de nomina con estos campos:

- `primer_mes_nomina` (1..12)
- `primer_anio_nomina` (1900..2100)

Regla funcional:

- Si el `periodo_inicio` de la nomina coincide con ese mes/anio, se aplica bootstrap usando `salario_acumulado` e `impuesto_acumulado` del empleado.
- Si no coincide, el sistema usa acumulados normales del sistema.

### Bloqueo de Edicion

La edicion de `primer_mes_nomina` y `primer_anio_nomina` queda bloqueada cuando existe al menos una nomina de la empresa en estado:

- `applied`
- `paid`

Si se intenta cambiar esos campos en ese escenario, el backend ignora el cambio, muestra advertencia y conserva los valores existentes.
