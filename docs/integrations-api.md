# API de integraciones

La API versionada está disponible bajo `/api/v1`. El endpoint `/health` es público; el resto exige un token `Bearer` creado con `payrollctl users create-token`. Los tokens se almacenan únicamente como hashes y pueden expirar o revocarse desde la base de datos.

Endpoints de lectura: `employees`, `payrolls`, `payrolls/<id>/results`, `reports` y `novelties`. La creación de novedades requiere el alcance `write`. Los usuarios no administradores solo reciben datos de las empresas asociadas a su cuenta.

La sincronización automática consume solo las monedas principales indicadas en `EXCHANGE_RATES_PRIMARY_CURRENCIES` (por defecto `EUR`), desde un proveedor JSON con `base`, `date` y `rates`; nunca importa el resto de la respuesta. Configure también `EXCHANGE_RATES_URL`, `EXCHANGE_RATES_BASE_CURRENCY` y, opcionalmente, `EXCHANGE_RATES_TIMEOUT_SECONDS` en `/etc/coati-payroll/exchange-rates.env`. El timer `ops/exchange-rates/coati-payroll-exchange-rates.timer` ejecuta el job diariamente. La carga manual se conserva siempre mediante `Tipos de Cambio > Nuevo Tipo de Cambio` o `Importar desde Excel`, y el CLI admite `--primary-currency` repetido para una ejecución puntual.
