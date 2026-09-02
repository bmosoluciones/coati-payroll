# Introducción

Coati Payroll es un motor para el calculo de planillas de pago, por diseño Coati Payroll no almacena calculos hardcoded, todos
los calculos que realiza el sistema deben configurables

Registros Maestros:

- Empleado
- Compañia
- Nomina
- Percepción
- Deducción
- Prestación

Una nomina (un payroll) agrupa empleados, percepciones, deducciones, prestaciones y una regla de devengo de vacaciones, una planilla (un payrun)
es un calculo de una nomina para período especifico.

Un planilla agrupa novedades para ese período.

Todos los calculos que el sistema realiza debe ser configurables, calculos complejos pueden editarse en linea, registrarse como un JSON y ese
JSON puede ser traducido a calculos seguros que python puede realizar.

## Regla de oro:

Coati Payroll no debe de harcodear ningun valor requerido para el calculo de una nomina, todos los calculos realizados y sus valores
deben ser configurables.

# Instrucciones

Si una tarea esta asociada a un issue en github se debe utilizar ese issue como bitacora del trabajo realizado, para ello
se pueden postear comentarios en el issue que aporte al analisis, solución y revisión del fix propuesto.

Se deben usar etiquetas para coordinar el trabajo con issues en github:

- needs-work: requiere trabajo adicional, posible falso positivo o un issue no verificado.
- fix-proposed: tiene un fix propuesto el cual aún requiere ser validado, puede pasar a dos estatus:
  -  fix-confirmed: el fix se considera correcto, robusto, bien implementado y con una covertura de pruebas unitarias completa.
  -  needs-work: el fix no esta completo y requiere trabajo adicional.
- fix: un issue con el tag fix-confirmed puede pasar a fixed y cerrarse si no hay trabajo adicional requerido.

## Control de calidad

Los controles de calidad black, ruff, mypy y flake8 no toman mucho tiempo y deben ejecutarse y los errores que reporten deben corregirse antes
de confirmar un commit.

Las pruebas unitarias relacionadas a la tarea actual se deben correr y las regresiones que surjan deben corregirse antes de confirmar un commit.

La suite completa de pruebas unitarias debe ejecutarse antes de hacer push al repositorio moto.

## Covertura de codigo 

Asegurar una covertura del 90% en codigo generado por LLM

## Validación de la tarea

No cerrar issues en github, siempre debe utilizarse un agente de planificación y ejecución y un agente independiente de QA para verificar el
trabajo, los issues deben de pasar al menos por dos agentes distintos antes de asegurar que un fix a sido confirmado.


