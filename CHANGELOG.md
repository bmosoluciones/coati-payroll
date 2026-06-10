# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.10.3] - 2026-06-10

### Changed

- Maintenance release.
- Updated Python dependencies: `cryptography`, `flask-reuploaded`, `sqlalchemy`, `weasyprint`.
- Updated Javascript dependencies: `bootstrap-icons`, `alpinejs`.

## [1.10.2] - 2026-05-16

### Changed

- Added `salario_gravable` / `salario_gravable_periodo` as calculation variables for formula and `ReglaCalculo` execution, derived from period salary after absence discounts plus perceptions configured as gravable.
- Updated payroll accumulation and recalculation rollback to use the same configured gravable-income basis, keeping tax accumulators consistent across recalculations.


## [1.10.0] - 2026-05-03

### Changed

 - Include PwA manifest

## [1.9.1] - 2026-03-05

### Fixed

 - Adjusted code long to avoid Text to long issue.

### Changed

 - Include vacations liability in details view.

### Fixed
 - Fix text to long issue in `tipo_planilla` table

## [1.9.0] - 2026-02-23

### Added

- Added a dedicated employee salary-change flow at `/employee/edit/<id>/salary` with a `Modificar Salario Base` action in employee edit view.
- Added salary change persistence in `HistorialSalario` when salary/currency updates are executed from the dedicated flow.
- Added payroll void action (`POST /planilla/<planilla_id>/nomina/<nomina_id>/anular`) for payrolls that are not in `applied`/`paid` status, with audit trail and cancellation reason.

### Changed

- Locked `salario_base` and `moneda` fields in regular employee edit (`/employee/edit/<id>`) and enforced server-side protection so those values cannot be changed through the standard employee update endpoint.
- Updated payroll detail/history views to render `Anulado` (`cancelled`) status and expose the `Anular` action when applicable.
- Clarified payroll overlap behavior so `cancelled` payrolls do not block creating new payroll runs for overlapping periods.
- Restricted payroll void operation to disallow cancellation while payroll is `calculating`, avoiding invalid state transitions during background processing.
- Added a visible warning when payroll is executed/recalculated with fewer days than expected for the payroll periodicity (for example, a monthly payroll calculated for a single day).
- Added `Var dias calculo` as a primary KPI in payroll comparison dashboard (`comparar nomina`) to highlight period-length changes between base and current payroll.

### Tests

- Added route-level coverage for payroll void action permissions, valid/invalid state transitions, and `Anular` button visibility in payroll detail.
- Re-validated overlap behavior with cancelled payrolls to ensure cancelled runs do not block new payroll generation for the same period.

### Fixed

- Adjusted payroll employee detail summary to display `Salario Base` net of absence discounts (`sueldo_base_historico - inasistencia_descuento`) for reclassified novelties.
- Adjusted payroll main detail table (`Detalle por Empleado`) to display `Salario Base` net of absence discounts (`sueldo_base_historico - inasistencia_descuento`).
- Updated payroll Excel export (`exportar-excel`) so `Total Ingresos` reflects period gross pay while preserving the reclassification-adjusted salary display column.
- Added an explicit warning when the first payroll run does not start at fiscal period start, recommending manual tax verification.
- Fixed payroll comparison approval banner to label the approving user clearly and avoid 404s by flashing and redirecting when a comparison payroll id is missing.
- Fixed suggested payroll period selector (`/planilla/<id>/ejecutar`) to safely handle multiple payroll records and ignore cancelled runs when computing the recommended start date.


## [1.8.1] - 2026-02-22

### Added

- Added payroll comparison flow with a dedicated route, comparison dashboard template, and a "Comparar con otra nómina" action from payroll detail.
- Added `NominaComparacion` model persistence for cached base-vs-actual comparison results, including freshness and approval metadata.
- Added `NominaComparisonService` with KPI generation for alerts, outliers, concept drivers, segmentation, structural changes, stability score, and vacation-rule comparisons.
- Added comparison-oriented indexes on `NominaEmpleado (nomina_id, empleado_id)` and `NominaDetalle (nomina_empleado_id, tipo, codigo)`.

### Changed

- Updated payroll recalculation flow to refresh/re-point comparison cache rows that referenced the replaced payroll id.
- Exposed `NominaComparisonService` through the planilla services package exports.

### Fixed

- Added race-safe comparison cache persistence by handling concurrent insert `IntegrityError` with rollback and cached-row re-read fallback.

### Tests

- Added unit tests for comparison KPI/statistical helpers, approval metadata helpers, and concurrent cache insert fallback handling.

## [1.8.0] - 2026-02-21

### Changed

- Moved base salary accounting configuration to company-level (`Empresa`) and exposed debit/credit account + description fields in company maintenance UI.
- Updated accounting voucher generation to resolve base salary accounts with company-first priority and planilla fallback for backward compatibility.
- Updated accounting configuration validation warnings to report missing base salary setup based on the effective source (empresa/planilla).
- Updated salary-payable usage in loan/advance accounting lines to reuse the same resolved base salary credit account.

### Added

- Added documentation for robust summarized voucher setup, including source-of-truth matrix for salario básico, percepciones, deducciones, prestaciones, and paid-vacation accrual liability.
- Edit html forms.
- Updated payroll novelties concept selectors to use only active concepts assigned to the payroll template (`Planilla`).
- Updated novelties deduction selector to exclude deduction types `tax` and `social_security`.

### Tests

- Added coverage for novelties selector filtering by planilla assignment, active state, and deduction type exclusion (`tax` / `social_security`).

## [1.7.3] - 2026-02-19

### Changed

- Replaced mid-year carry-in bootstrap strategy from employee-level implementation fields to company-level configuration using `primer_mes_nomina` and `primer_anio_nomina`.
- Added bootstrap period fields to company management forms and company edit views.
- Added server-side lock for company bootstrap period fields when payroll runs already exist in `applied` or `paid` status.
- Updated payroll calculation flow so employee carry-in values are applied only when `periodo_inicio` matches the company's configured first payroll period.
- Updated accumulation bootstrap to derive `periodos_procesados` from fiscal start month and payroll periodicity (`periodos_por_anio`) without hardcoded assumptions.
- Added an initial implementation helper at `/settings/helpers/` to import summarized accounting voucher account mappings from an Excel template using user-visible names (not internal database IDs) for companies, earnings, deductions, benefits, and vacation policies.

### Fixed

- Fixed carry-in behavior to avoid reapplying employee bootstrap balances outside the configured initial company period.
- Fixed company form rendering to support disabled fields in `render_field` macro, ensuring lock UX works correctly.

### Documentation

- Updated employer docs to describe company-level bootstrap configuration and lock behavior.
- Updated employee docs to remove legacy implementation year/month fields and keep only carry-in balances.
- Clarified that implementation period is not configured in global calculation settings.

### Tests

- Updated repository tests for company-level bootstrap behavior and derived initial period counts.
- Added company view test coverage for bootstrap field lock when payroll is already applied.


## [1.7.2] - 2026-02-18

### Changed

- Improved annual accumulation bootstrap logic for mid-year payroll implementations by applying employee-provided initial balances only during the configured implementation fiscal year.
- Added explicit implementer guidance for fiscal mid-year cutovers with accumulated salary and retained income tax balances.

### Fixed

- Fixed IR carry-in initialization so `impuesto_acumulado` is now mapped to `impuesto_retenido_acumulado` (retained tax), not to pre-tax deductions.
- Fixed initial processed-period bootstrap for fiscal calculations by deriving `periodos_procesados` from `mes_ultimo_cierre` during implementation cutovers.

### Tests

- Added repository-level tests to validate mid-year bootstrap balances and prevent reapplying initial carry-in values in subsequent fiscal years.


## [1.7.1] - 2026-02-17

### Fixed

- Regenerated audit vouchers during payroll apply after prestaciones/vacation side effects, ensuring persisted accounting lines include paid vacation liability for detailed voucher exports.
- Made `aplicar_nomina` transactional around side effects and voucher regeneration so failures roll back the apply operation and avoid partial persistence.
- Reused a shared voucher-regeneration helper in the manual regeneration route to keep calculation date/user behavior consistent.
- Updated payroll Excel export (`exportar-excel`) to a dynamic 5-section layout with extended header metadata, generic reclassification handling, and vacation liability in labor benefits.

### Tests

- Added route-level coverage to verify payroll apply persists a voucher and rolls back correctly when voucher regeneration fails.
- Updated vacation accrual end-to-end validation to assert `vacation_liability` lines are available from persisted detailed voucher data after applying payroll, without manual regeneration.


## [1.7.0] - 2026-02-17

### Added

- **Docker deployment architecture**: Added `PROCESS_ROLE` environment variable to support three deployment options:
  - `PROCESS_ROLE=web`: Web-only container (no worker) for separate web/worker deployments
  - `PROCESS_ROLE=worker`: Dedicated Dramatiq worker container
  - `PROCESS_ROLE=all`: All-in-one container with app + worker (default, backward compatible)
- **Systemd deployment**: Added example unit files for production systemd deployments:
  - `systemd/coati-payroll.service`: Web application service
  - `systemd/coati-payroll-worker.service`: Dedicated Dramatiq worker service
  - `systemd/README.md`: Complete installation and configuration guide
- Comprehensive deployment documentation in README.md covering:
  - Option 1: Single container without queue processing (development)
  - Option 2: All-in-one container with background processing (small/medium deployments)
  - Option 3: Separate web/worker containers with Redis (production, scalable)

### Changed

- Restricted payroll background processing to Dramatiq+Redis only; removed operational fallback to Huey.
- Updated queue and background payroll documentation to reflect Dramatiq+Redis as the only supported background backend and Noop degradation when Redis is unavailable.
- Removed `huey` from runtime dependencies in `requirements.txt`.
- Removed legacy `coati_payroll/queue/drivers/huey_driver.py` and remaining runtime references to Huey.
- Refactored `docker-entrypoint.sh` to support role-based container startup with proper database initialization only for web/all roles.

## [1.6.0] - 2026-02-15

### Changed

- Deferred prestaciones (`PrestacionAcumulada`) ledger side effects to the payroll apply step (`applied`/`paid`) so draft/generated recalculations do not mutate balances.

### Fixed

- Added defensive cleanup for legacy `PrestacionAcumulada` rows tied to recalculated source payrolls to avoid duplicate benefit balances.

### Tests

- Updated unit and validation tests to assert prestaciones ledger updates only happen on payroll apply/paid transitions and remain idempotent across draft recalculations.


## [1.5.0] - 2026-02-15

### Added

- Added `mes_inicio_fiscal` to `Planilla` and exposed it in the payroll template form as a month selector (January-December).
- Added `prorate_by_period_days` to `VacationPolicy` to control period-day proration for periodic accruals.

### Changed

- Updated payroll template create/edit/clone flows to persist and propagate `mes_inicio_fiscal`.
- Updated fiscal-period resolution in payroll accumulation and annual lookup logic to use `Planilla.mes_inicio_fiscal` as the source of truth.
- Updated monthly fiscal progression inputs used by calculation rules to align with the planilla fiscal-start month.
- Deferred vacation ledger side effects to the payroll apply step to avoid mutating balances during generation.
- Rounded vacation ledger accruals to 2 decimal places for balance consistency.
- Updated Nicaragua default vacation policy to accrue full monthly rate regardless of month length.

### Fixed

- Allowed recalculating non-approved payrolls for the same period by excluding the source payroll from overlap and duplicate-period validation checks.
- Fixed periodic vacation accrual proration so monthly policies on biweekly payrolls accrue proportionally by worked days in the period.
- Fixed calculation rules issues.
- Cleaned vacation ledger entries tied to recalculated payrolls to prevent duplicate accruals and recomputed balances.


## [1.4.1] - 2026-02-13

### Changed

- Hardened deletion safeguards: companies cannot be deleted when they have active employee links or associated payroll runs, and payroll templates (`Planilla`) cannot be deleted when they have associated payruns (`Nomina`).

### Fixed

- Fixed missing CSRF tokens in 49+ POST forms across 23 templates to prevent cross-site request forgery attacks.
- Fixed schema initialization in `flask database init` by resolving a duplicate index name collision on `liquidacion.concepto_id` that could leave tables like `vacation_account` uncreated.
- Fixed vacation policy form validation so `Tasa de Acumulación` and `Días Mínimos de Servicio` are now optional and default to `0` when omitted.

## [1.4.0] - 2026-02-12

### Added

- Added configurable payment percentage for paid vacations via `porcentaje_pago_vacaciones` field in `VacationPolicy` (default 100%).
- Added `son_vacaciones_pagadas` flag to `VacationPolicy` to mark policies that should generate accounting liability entries.
- Added accounting configuration fields to `VacationPolicy`: `cuenta_debito_vacaciones_pagadas`, `cuenta_credito_vacaciones_pagadas`, and their descriptions.
- Added `vacation_policy_id` foreign key to `Planilla` model to allow explicit binding of payroll to vacation accrual policy.
- Extended `VacationService` to prioritize planilla-bound vacation policy when resolving employee vacation accounts.
- Extended `AccountingVoucherService` to generate vacation liability accounting lines for paid vacation policies during payroll execution.

### Changed

- Vacation payment calculation now applies configurable percentage: `monto = (salario_base / dias_base) * units * (porcentaje / 100)`.
- Vacation approval workflow now only validates balance; actual balance deduction deferred to payroll execution via `NominaNovedad` for better traceability.
- Planilla creation/edit forms now include vacation policy selector with scope-aware choices (planilla/empresa/global).

### Fixed

- Fixed SQLAlchemy "multiple foreign key paths" error in bidirectional `Planilla`-`VacationPolicy` relationship by specifying explicit `foreign_keys` parameter.
- Fixed Alembic migration compatibility with SQLite by using `op.batch_alter_table()` for foreign key operations instead of direct `op.create_foreign_key()` and `op.drop_constraint()`.

## [1.3.3] - 2026-02-11

### Fixed
 - Fix accounting voucher issues.

## [1.3.2] - 2026-02-11

### Fixed
 - Duplica payroll UI

## [1.3.1] - 2026-02-10


### Added

- Added planilla cloning from the web UI (list action) to duplicate payroll templates including perceptions, deductions, and benefits.

### Changed

- Added bilingual periodicity support in salary calculation for Spanish/English terms (`mensual`/`monthly`, `quincenal`/`biweekly`).
- Moved planilla clone business logic to the planilla service layer and exposed it through a dedicated route.

### Tests

- Added route and UI tests for planilla cloning (authentication, visibility, and association-copy behavior).
- Updated prestaciones accumulation validation expectations for full-calendar-month payroll periods.

## [1.3.0] - 2026-02-10

### Added

- Added date calculation functions to the formula engine: `days_between()`, `max_date()`, and `min_date()`.
- Added support for date and string input types in the formula engine.

### Changed

- Updated formula engine evaluation, execution context, and results handling to support non-Decimal values.
- Preserved date/string inputs without Decimal conversion in initial variable preparation and step storage.

## [1.2.0] - 2026-02-09

### Changed

- Added concept-level absence defaults to `Percepcion` and `Deduccion` via `es_inasistencia` and `descontar_pago_inasistencia`.
- Updated payroll concept forms and shared concept UI to configure these absence-default flags.
- Updated concept persistence/audit change detection to store and track the new absence-default flags.
- Updated novelty backend creation/update to apply defaults from the selected concept when absence flags are omitted, while preserving explicit payload values.
- Applied the same absence-default resolution to vacation-generated novelties and demo novelty creation for consistent behavior across entry points.
- Added route-level tests for novelty creation to validate default propagation and explicit override behavior.
- Refactored novelty absence-default resolution into a shared utility module to simplify reuse and enable isolated unit testing.
- Added focused unit tests for absence-default resolution and explicit-form override behavior without requiring full view/bootstrap fixtures.

## [1.1.1] - 2026-02-09

### Changed

- Add absence tracking (absences)

## [1.1.0] - 2026-02-09

### Added

- Added a vacation-to-payroll novelty bridge with UI support to apply approved vacations directly into payroll runs.
- Added accounting/reporting flags for perceptions and deductions to invert postings and control report income presentation.

### Changed

- Added absence flags to novelties and applied unpaid-absence salary discounts with a distinct `salario_neto_inasistencia` formula input.
- Standardized the disability novelty concept code to `DISABILITY` for formula sources.
- Updated accounting voucher generation to honor inverted debit/credit configuration for applicable perceptions and deductions.

### Fixed

- Fixed vacation approvals to validate balances, deduct immediately, and log ledger entries consistently.


## [1.0.6] - 2026-02-09

### Changed

- Refactored modules across CLI, queue drivers, payroll processing, and view layers to align with the active lint/type validation baseline.
- Standardized control-flow patterns, SQLAlchemy boolean predicates, import organization, and variable naming to reduce static-analysis false positives.
- Updated `pylint` configuration with explicit non-critical exclusions used by this codebase and its framework integration points.

### CI

- Added `pylint -j 0 coati_payroll` to `.github/workflows/python-package.yml`.
- Added `dev/lint.sh` to run the full local validation stack (`black`, `ruff`, `flake8`, `pylint`, `mypy`, `pytest`, and `pytest -m validation`).

## [1.0.5] - 2026-02-08

### Changed

- Marked the codebase as `mypy` compliant for the `coati_payroll` package under the current type-checking configuration.
- Integrated `mypy` execution into the CI workflow to enforce type checks on every push and pull request.

## [1.0.4] - 2026-02-08

### Fixed

- Preserved `NominaNovedad` records during payroll recalculation to prevent loss of payroll master data.
- Re-linked preserved novelties to the new recalculated payroll run instead of deleting them with old calculation records.
- Added defensive regression tests to ensure novelties are not deleted in future recalculation changes.

## [1.0.3] - 2026-02-08

### Fixed

- Corrected an error in payrun calculation.

## [1.0.2] - 2026-02-07

### Executive Summary

Release 1.0.2 consolidates refactors across payroll processing, accounting vouchers, and liquidation flows to improve determinism, validation strictness, and operational resilience. It also expands the formula engine safety surface and strengthens queue processing and recovery behavior, with supporting test coverage updates.

### Changed

- Refactored queue processing, accounting voucher generation, and payroll execution for clearer error handling and progress tracking.
- Hardened formula engine evaluation, lookup validation, and rounding utilities to improve determinism and type safety.
- Updated liquidation, interest, and vacation services with tighter workflows and consistent snapshot and policy handling.
- Refined UI flows and planilla export/service behaviors to align with revised validation and state transitions.

### Tests

- Extended unit and integration coverage for formula engine, payroll defensive mechanisms, vouchers, vacations, and routes.

## [1.0.1] - 2026-02-06

### Security

- Hardened production startup checks and configuration validation to prevent insecure deployments.
- Enforced rate limiting and upload size safeguards in production while keeping tests isolated.

### Changed

- Upgraded the data layer and normalized enum persistence for more consistent behavior.
- Improved RBAC, auditing, and workflow handling across payroll, loans, and vacation flows.
- Refined CLI, logging, and bootstrap routines to reduce noise and require explicit schema management.

### Fixed

- Resolved edge cases in payroll calculations, loan handling, and vacation workflows.
- Corrected database initialization and connection handling in Docker/runtime environments.

### Documentation

- Expanded operational guides and documented calculation options and edge cases.

## [1.0.0] - 2026-02-02

### Added

- **Formula Engine**: Complete formula evaluation engine with support for:
  - Progressive tax tables with configurable brackets
  - Conditional steps and calculations
  - Variable assignments and expressions
  - Safe operator evaluation (AST-based)
  - Schema validation and security checks

- **Vacation Management Module**: Full-featured vacation system including:
  - Configurable vacation policies
  - Employee vacation accounts with accrual tracking
  - Vacation requests and approval workflow
  - Vacation ledger for complete audit trail

- **Payroll Engine Refactoring**: Clean architecture implementation with:
  - Domain models (PayrollContext, EmployeeCalculation, CalculationItems)
  - Validators (Planilla, Employee, Period, Currency)
  - Calculators (Salary, Concept, Perception, Deduction, Benefit, ExchangeRate)
  - Processors (Loan, Accumulation, Vacation, Novelty, Accounting)
  - Repositories (Planilla, Employee, Acumulado, Novelty, ExchangeRate, Config)
  - Services (PayrollExecution, EmployeeProcessing, AccountingVoucher)

- **Role-Based Access Control (RBAC)**: Permission system with Admin, HR, and Audit roles

- **Reporting System**: Custom reports with role-based permissions and execution audit

- **Queue System**: Background processing for large payrolls with:
  - Dramatiq + Redis for production
  - Huey + Filesystem for development
  - Automatic backend selection

- **Internationalization (i18n)**: Multi-language support with translation files

- **Company-Employee-Planilla Validation**: Internal control ensuring employees and planillas belong to the same company

- **CLI Tool (payrollctl)**: Command-line interface for:
  - System operations (status, check, info, env)
  - Database management (init, seed, backup, restore, migrate)
  - User management (list, create, disable, reset-password)
  - Cache management (clear, warm, status)
  - Maintenance tasks (cleanup-sessions, cleanup-temp, run-jobs)

### Changed

- **Social Contract Compliance**: Complete refactoring to ensure jurisdiction-agnostic design:
  - All jurisdiction-specific examples renamed to generic identifiers
  - Backward-compatible aliases maintained for migration
  - Clear disclaimers added to all example data
  - Documentation updated to reflect generic nature

- **Schema Editor**: Improved JSON schema editor with proper serialization handling

- **Default Values**: Added disclaimers clarifying that default values are for initial adoption only and do not represent legal rules

### Fixed

- Database initialization issues with orphaned indexes
- JavaScript serialization errors in schema editor template
- MutableDict handling for JSON fields in templates

### Security

- Safe expression evaluation using AST visitor pattern
- Input validation on all formula engine operations
- Role-based access control on all sensitive operations

### Documentation

- Complete README with installation, configuration, and usage guides
- Social Contract defining project scope and responsibilities
- Architecture documentation with directory structure
- API documentation for CLI commands
- Local implementation guides (docs/local_guides/)
