![Logo](https://raw.githubusercontent.com/bmosoluciones/coati-payroll/refs/heads/main/coati_payroll/static/logo/Icono-small.png)

# Coati Payroll

![PyPI - License](https://img.shields.io/badge/License-Apache%202.0-brightgreen?logo=apache&logoColor=white)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg?logo=python&logoColor=white)
[![Unit Testing](https://github.com/bmosoluciones/coati-payroll/actions/workflows/python-package.yml/badge.svg)](https://github.com/bmosoluciones/coati-payroll/actions/workflows/python-package.yml)
[![codecov](https://codecov.io/github/bmosoluciones/coati-payroll/graph/badge.svg?token=gT6jVct2KT)](https://codecov.io/github/bmosoluciones/coati-payroll)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=bmosoluciones_coati-payroll&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=bmosoluciones_coati-payroll)
[![Code style: black](https://img.shields.io/badge/Python%20code%20style-black-000000.svg)](https://github.com/psf/black)
[![Code style: Prettier](https://img.shields.io/badge/HTML%20code%20style-prettier-ff69b4.svg)](https://github.com/prettier/prettier)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A jurisdiction-agnostic payroll calculation engine developed by BMO Soluciones, S.A.

![ScreenShot](https://raw.githubusercontent.com/bmosoluciones/coati-payroll/refs/heads/main/docs/CoatiPayrollSystem.png)

-----------

<table>
  <tr>
    <td><a href="https://github.com/bmosoluciones/now-lms/blob/main/docs/images/bmo.png"><img src="https://raw.githubusercontent.com/bmosoluciones/coati-payroll/refs/heads/main/docs/Coaty-Sistema-de-Planillas-08-08-2026_12_21_PM.png" alt="BMO theme" width="140"></a></td>
    <td><a href="https://github.com/bmosoluciones/now-lms/blob/main/docs/images/now-lms.png"><img src="https://raw.githubusercontent.com/bmosoluciones/coati-payroll/refs/heads/main/docs/Coaty-Sistema-de-Planillas-08-08-2026_12_23_PM.png" alt="NOW LMS landing page" width="140"></a></td>
    <td><a href="https://github.com/bmosoluciones/now-lms/blob/main/docs/images/excel.png"><img src="https://raw.githubusercontent.com/bmosoluciones/coati-payroll/refs/heads/main/docs/Coaty-Sistema-de-Planillas-08-08-2026_12_24_PM.png" alt="Excel theme" width="140"></a></td>
  </tr>
</table>

-----------

**Coati Payroll** is a flexible and extensible payroll calculation engine, completely jurisdiction-agnostic. The system is designed so that organizations and implementers can define their own payroll rules through configuration, without the need to modify the source code.

The engine does not incorporate hardcoded legal rules. All earnings, deductions, benefits, taxes, and other payroll concepts exist only if the implementer configures them.

> **Important**: This project is governed by a [Social Contract](SOCIAL_CONTRACT.md) that clearly defines its scope, purpose, and limitations. Please read it before using the system in production.

## Disclaimer and scope

```
The calculation engine may not be suitable for all possible use cases. The development team
is happy to collaborate with interested parties to expand the engine's capabilities so it can
cover as many use cases as possible. This project is offered under an open-source license,
as-is, without warranties of fitness for any particular purpose.
```

## Key Features

- **Jurisdiction-Agnostic**: No hardcoded legal rules; all payroll logic is defined through configuration
- **Configurable Calculation Engine**: Payroll processing with fully configurable formulas and schemas
- **Flexible Calculation Rules**: Rule system that allows implementing any payroll logic through configuration
- **Multi-company**: Manage payrolls for multiple companies or entities from a single system
- **Employee Management**: Complete registration of personal, work, and salary information
- **Custom Fields**: Extend employee information with custom fields
- **Configurable Earnings**: Define any type of additional income (bonuses, commissions, overtime, etc.)
- **Priority-Based Deductions**: Configure deductions in priority order according to your needs
- **Employer Benefits**: Configure benefits and employer contributions as required
- **Planilla Cloning (Web UI)**: Duplicate an existing payroll template from the planilla list, including perceptions, deductions, and benefits
- **Loans and Advances**: Loan control with automatic installment deduction
- **Multi-currency**: Support for multiple currencies with exchange rates
- **Background Processing**: Queue system for large payrolls with Dramatiq+Redis
- **Vacation Management**: Complete module for vacation accrual, usage, and audit with configurable policies
- **Role-Based Access Control (RBAC)**: Permission system with Admin, HR, and Audit roles
- **Reporting System**: Custom reports with role-based permissions and execution audit
- **Internationalization**: Multi-language support with interface and content translation
- **Periodicidad Compatibility**: Salary calculation accepts both Spanish and English periodicity terms (`mensual`/`monthly`, `quincenal`/`biweekly`)

## Quick Installation

### Requirements

- Python 3.11 or higher
- pip (Python package manager)

### Steps

1. **Clone the repository**

```bash
git clone https://github.com/bmosoluciones/coati-payroll.git
cd coati-payroll
```

2. **Create and activate virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Run the application**

```bash
python app.py
```

5. **Access the system**

Open your browser at `http://localhost:5000`

**Default credentials:**
- User: `coati-admin`
- Password: `coati-admin`

> **Important**: Change the default credentials in production environments.

### Docker Installation

Coati Payroll supports three deployment architectures with Docker:

#### Architecture Options

1. **Option 1: Single container without queue processing** - Simplest setup for development or small deployments
2. **Option 2: Single container with background processing** - All-in-one deployment with app + worker in same container
3. **Option 3: Separate containers (Production)** - Web and worker in separate containers for scalability

---

#### Option 1: Single Container Without Queue Processing

For development or when background processing is not needed:

```bash
# Build the image
docker build -t coati-payroll:latest .

# Run without queue processing
docker run -d -p 5000:5000 \
  -e FLASK_ENV=development \
  -e QUEUE_ENABLED=0 \
  --name coati-payroll \
  coati-payroll:latest
```

**Behavior**: All payroll calculations execute synchronously. No Redis required.

---

#### Option 2: Single Container With Background Processing (All-in-one)

For small to medium deployments where separating web/worker isn't necessary:

```bash
# Start Redis
docker run -d -p 6379:6379 --name redis redis:alpine

# Start Coati Payroll with worker in same container
docker run -d -p 5000:5000 \
  -e FLASK_ENV=production \
  -e DATABASE_URL="postgresql://user:password@host:5432/coati_payroll" \
  -e SECRET_KEY="your-secret-key-here" \
  -e ADMIN_USER="admin" \
  -e ADMIN_PASSWORD="secure-password" \
  -e QUEUE_ENABLED=1 \
  -e PROCESS_ROLE=all \
  -e REDIS_URL="redis://redis:6379/0" \
  -e BACKGROUND_PAYROLL_THRESHOLD=100 \
  -e DRAMATIQ_WORKER_THREADS=8 \
  -e DRAMATIQ_WORKER_PROCESSES=2 \
  --link redis:redis \
  --name coati-payroll \
  coati-payroll:latest
```

**Behavior**: 
- Web app serves requests
- Dramatiq worker runs in background in same container
- Suitable for deployments with moderate load
- Default behavior when `PROCESS_ROLE` is not specified

**Verify worker started**:
```bash
docker logs coati-payroll
# Should show: "[entrypoint] Starting Dramatiq worker in background (all-in-one mode, threads=8, processes=2)"
```

---

#### Option 3: Separate Containers (Recommended for Production)

For production deployments requiring scalability and fault isolation:

**Using Docker Compose** (recommended):

A production-ready `docker-compose.yml` is provided in the repository with:
- **Nginx reverse proxy** (serves static files and handles HTTPS)
- PostgreSQL database (with MySQL as commented alternative)
- Redis for queue and cache
- Dedicated worker container
- Web application container (WSGI server)
- Certbot for Let's Encrypt SSL certificates (optional)
- Health checks and proper service dependencies

**Quick start**:

```bash
# 1. Copy and customize environment variables
cp .env.example .env
# Edit .env and set secure passwords and secrets!

# 2. Start all services
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Access the application
# HTTP: http://localhost or http://your-server-ip
# HTTPS: https://your-domain.com (after configuring SSL)
```

**Static files are served by nginx**, not the WSGI server. This provides:
- Faster delivery of CSS, JavaScript, and images
- Reduced load on the application server
- Better caching and compression

**HTTPS setup with Let's Encrypt**:

For production deployments with SSL certificates:

```bash
# Run the Let's Encrypt initialization script
chmod +x nginx/init-letsencrypt.sh
./nginx/init-letsencrypt.sh your-domain.com your-email@example.com

# Edit nginx/nginx.conf and uncomment the HTTPS server block
# Uncomment the certbot service in docker-compose.yml

# Restart services
docker-compose restart nginx
```

See `nginx/README.md` for detailed HTTPS configuration instructions.

**Scale workers** (if you need more processing capacity):
```bash
docker-compose up -d --scale worker=3
```

**Using MySQL instead of PostgreSQL**:
Edit `docker-compose.yml` and:
1. Comment out the `postgres` service
2. Uncomment the `mysql` service
3. Update `DATABASE_URL` in `web` and `worker` services
4. Update `depends_on` to reference `mysql` instead of `postgres`

**Or using individual containers**:

```bash
# Build image
docker build -t coati-payroll:latest .

# Start infrastructure
docker run -d --name redis redis:alpine
docker run -d --name postgres -e POSTGRES_PASSWORD=changeme postgres:15-alpine

# Start web container (no worker)
docker run -d -p 5000:5000 \
  --name coati-web \
  -e PROCESS_ROLE=web \
  -e QUEUE_ENABLED=1 \
  -e REDIS_URL=redis://redis:6379/0 \
  -e DATABASE_URL=postgresql://postgres:changeme@postgres:5432/postgres \
  --link redis:redis \
  --link postgres:postgres \
  coati-payroll:latest

# Start worker container (dedicated)
docker run -d \
  --name coati-worker \
  -e PROCESS_ROLE=worker \
  -e QUEUE_ENABLED=1 \
  -e REDIS_URL=redis://redis:6379/0 \
  -e DATABASE_URL=postgresql://postgres:changeme@postgres:5432/postgres \
  -e DRAMATIQ_WORKER_THREADS=8 \
  -e DRAMATIQ_WORKER_PROCESSES=2 \
  --link redis:redis \
  --link postgres:postgres \
  coati-payroll:latest
```

**Benefits of Option 3**:
- Scale web and worker independently
- Isolate failures (worker crash doesn't affect web)
- Optimize resource allocation per component
- Standard production architecture pattern

**Verify services**:
```bash
# Check web container
docker logs coati-web
# Should show: "[entrypoint] Starting app in web-only mode (no worker)"

# Check worker container
docker logs coati-worker
# Should show: "[entrypoint] Starting Dramatiq worker (dedicated mode, threads=8, processes=2)"
```

---

#### Environment Variables Reference

| Variable | Description | Default | Required for |
|----------|-------------|---------|--------------|
| `PROCESS_ROLE` | Container role: `web`, `worker`, or `all` | `all` | Options 2, 3 |
| `QUEUE_ENABLED` | Enable queue system | `1` | Options 2, 3 |
| `REDIS_URL` | Redis connection string | - | Options 2, 3 |
| `BACKGROUND_PAYROLL_THRESHOLD` | Min employees for background processing | `100` | Options 2, 3 |
| `DRAMATIQ_WORKER_THREADS` | Worker threads per process | `8` | Options 2, 3 |
| `DRAMATIQ_WORKER_PROCESSES` | Worker processes | `2` | Options 2, 3 |

**Access the system**: Open your browser at `http://localhost:5000`

## Documentation

Complete documentation is available in the `docs/` directory and can be generated with MkDocs:

```bash
# Install documentation dependencies
pip install -r docs.txt

# Serve documentation locally
mkdocs serve

# Generate static documentation
mkdocs build
```

### Documentation Contents

- **[Quick Start Guide](docs/guia/inicio-rapido.md)**: 15 minutes from installation to your first payroll - ideal for evaluating the system
- **Installation Guide**: Requirements, installation, and initial configuration
- **User Guide**: Users, companies, currencies, employees, custom fields, payroll concepts, calculation rules, loans, vacations, accounting configuration
- **Complete Tutorial**: Step by step to configure and run a payroll with all components
- **Advanced Features**: 
  - Queue system and background processing
  - Database compatibility (SQLite, PostgreSQL, MySQL/MariaDB)
  - Role-based access control (RBAC)
  - Vacation management with configurable policies
  - Custom reporting system
  - Internationalization and translation
- **Reference**: Glossary, frequently asked questions, exchange rate import

## Architecture

```
coati/
├── app.py                 # Application entry point
├── coati_payroll/         # Main module
│   ├── __init__.py        # Flask application factory
│   ├── model.py           # Database models (SQLAlchemy)
│   ├── nomina_engine/     # Payroll calculation engine (refactored)
│   │   ├── __init__.py
│   │   ├── engine.py      # Main orchestrator
│   │   ├── domain/        # Domain models
│   │   │   ├── payroll_context.py
│   │   │   ├── employee_calculation.py
│   │   │   └── calculation_items.py
│   │   ├── validators/    # Validations
│   │   │   ├── base_validator.py
│   │   │   ├── planilla_validator.py
│   │   │   ├── employee_validator.py
│   │   │   ├── period_validator.py
│   │   │   └── currency_validator.py
│   │   ├── calculators/   # Calculations
│   │   │   ├── salary_calculator.py
│   │   │   ├── concept_calculator.py
│   │   │   ├── perception_calculator.py
│   │   │   ├── deduction_calculator.py
│   │   │   ├── benefit_calculator.py
│   │   │   └── exchange_rate_calculator.py
│   │   ├── processors/    # Specific processors
│   │   │   ├── loan_processor.py
│   │   │   ├── accumulation_processor.py
│   │   │   ├── vacation_processor.py
│   │   │   ├── novelty_processor.py
│   │   │   └── accounting_processor.py
│   │   ├── repositories/  # Data access
│   │   │   ├── base_repository.py
│   │   │   ├── planilla_repository.py
│   │   │   ├── employee_repository.py
│   │   │   ├── acumulado_repository.py
│   │   │   ├── novelty_repository.py
│   │   │   ├── exchange_rate_repository.py
│   │   │   └── config_repository.py
│   │   ├── services/      # Business services
│   │   │   ├── payroll_execution_service.py
│   │   │   └── employee_processing_service.py
│   │   └── results/       # Results and DTOs
│   │       ├── payroll_result.py
│   │       ├── validation_result.py
│   │       └── error_result.py
│   ├── formula_engine/    # Formula engine (refactored)
│   │   ├── __init__.py
│   │   ├── engine.py      # Main orchestrator
│   │   ├── exceptions.py  # Custom exceptions
│   │   ├── data_sources.py # Available data sources
│   │   ├── novelty_codes.py # Novelty codes
│   │   ├── ast/           # Expression evaluation (Visitor pattern)
│   │   │   ├── ast_visitor.py
│   │   │   ├── expression_evaluator.py
│   │   │   ├── safe_operators.py
│   │   │   └── type_converter.py
│   │   ├── validation/    # Validations
│   │   │   ├── schema_validator.py
│   │   │   ├── tax_table_validator.py
│   │   │   └── security_validator.py
│   │   ├── steps/         # Step types (Strategy pattern)
│   │   │   ├── base_step.py
│   │   │   ├── calculation_step.py
│   │   │   ├── conditional_step.py
│   │   │   ├── tax_lookup_step.py
│   │   │   ├── assignment_step.py
│   │   │   └── step_factory.py
│   │   ├── tables/        # Tax tables
│   │   │   ├── tax_table.py
│   │   │   ├── bracket_calculator.py
│   │   │   └── table_lookup.py
│   │   ├── execution/     # Execution context
│   │   │   ├── execution_context.py
│   │   │   ├── step_executor.py
│   │   │   └── variable_store.py
│   │   └── results/       # Results
│   │       └── execution_result.py
│   ├── formula_engine_examples.py # Schema examples
│   ├── vacation_service.py # Vacation management service
│   ├── rbac.py            # Role-based access control
│   ├── report_engine.py   # Reporting engine
│   ├── forms.py           # WTForms forms
│   ├── cli.py             # Command-line interface (payrollctl)
│   ├── queue/             # Queue system (Dramatiq+Redis)
│   │   ├── driver.py
│   │   ├── selector.py
│   │   ├── tasks.py
│   │   └── drivers/
│   ├── vistas/            # Views/Controllers (Blueprints)
│   │   ├── planilla/      # Payroll module
│   │   └── [other modules]
│   ├── templates/         # HTML templates (Jinja2)
│   ├── translations/      # Translation files (i18n)
│   └── static/            # Static files
├── docs/                  # MkDocs documentation
├── requirements.txt       # Production dependencies
├── development.txt        # Development dependencies
└── docs.txt               # Documentation dependencies
```

## Configuration

### Command Line Interface (CLI)

The system includes the `payrollctl` tool for common administrative tasks. You can also use `flask` for built-in commands.

**System Operations:**

```bash
# View system status
payrollctl system status

# Run system checks
payrollctl system check

# View system information
payrollctl system info

# View environment variables
payrollctl system env
```

**Database Management:**

```bash
# View database status
payrollctl database status

# Initialize database and create admin user
payrollctl database init

# Load initial data (currencies, concepts, etc.)
payrollctl database seed

# Create database backup using native tools
# SQLite: Copy file | PostgreSQL: pg_dump | MySQL: mysqldump
payrollctl database backup -o backup_$(date +%Y%m%d).sql

# Restore database from backup
payrollctl database restore backup.db

# Database migration (requires flask-migrate)
payrollctl database migrate
payrollctl database upgrade

# Drop all tables (CAUTION!)
payrollctl database drop
```

**User Management:**

```bash
# List all users
payrollctl users list

# Create a new user
payrollctl users create

# Disable a user
payrollctl users disable username

# Reset password
payrollctl users reset-password username

# Create or update admin user (disables other admins)
payrollctl users set-admin
```

**Cache Management:**

```bash
# Clear application caches
payrollctl cache clear

# Warm up caches
payrollctl cache warm

# View cache status
payrollctl cache status
```

**Maintenance Tasks:**

```bash
# Clean up expired sessions
payrollctl maintenance cleanup-sessions

# Clean up report exports older than seven days (set COATI_TEMP_RETENTION_DAYS to change it)
payrollctl maintenance cleanup-temp

# Background jobs are processed by a Dramatiq worker; `maintenance run-jobs` intentionally exits with an error.
```

**Diagnostics and Debugging:**

```bash
# View application configuration
payrollctl debug config

# List all application routes
payrollctl debug routes
```

**Note**: All commands also work with `flask` (e.g., `flask system status`).

**Automated Backups**: To configure automatic daily backups with systemd timers, see [Automated Backups Guide](docs/automated-backups.md).

### Environment Variables

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `DATABASE_URL` | Database connection URI | Local SQLite |
| `SECRET_KEY` | Secret key for sessions | Auto-generated |
| `ADMIN_USER` | Initial admin user | `coati-admin` |
| `ADMIN_PASSWORD` | Admin password | `coati-admin` |
| `PORT` | Application port | `5000` |
| `SESSION_REDIS_URL` | Redis URL for sessions | None (uses SQLAlchemy) |
| `REDIS_URL` | Redis URL for queue system | None (background disabled) |
| `QUEUE_ENABLED` | Enable queue system | `1` |
| `BACKGROUND_PAYROLL_THRESHOLD` | Employee threshold for background processing | `100` |

### Database

The system supports:
- **SQLite**: For development and testing (default)
- **PostgreSQL**: Recommended for production
- **MySQL/MariaDB**: Production alternative

The system is designed to be **database engine agnostic**. For more details on compatibility and configuration, see the [Database Compatibility Guide](docs/database-compatibility.md).

### Queue System

For long-running operations, the system includes a **background process queue system**:

- **Dramatiq + Redis**: Required for background processing
- **Automatic degradation**: If Redis is unavailable, background processing is disabled and payrolls execute synchronously
- **Parallel processing**: Large payrolls (above threshold) are automatically processed in the background when queue is enabled
- **Real-time feedback**: Task progress tracking

For more information, see the [Queue System Documentation](docs/queue_system.md) and [Background Payroll Processing](docs/background-payroll-processing.md).

## Workflow

```mermaid
graph LR
    A[Configure Currencies] --> B[Create Earnings/Deductions/Benefits]
    B --> C[Register Employees]
    C --> D[Create Payroll]
    D --> E[Assign Components]
    E --> F[Execute Payroll]
    F --> G[Review and Approve]
    G --> H[Apply Payroll]
```

## Payroll Calculation

The payroll engine processes in this order:

1. **Base Salary**: Salary defined for the employee according to the payroll period
2. **Earnings**: Added to base salary → Gross Salary
3. **Deductions**: Subtracted in priority order → Net Salary
4. **Benefits**: Calculated as employer costs (do not affect net salary)

### Illustrative Calculation Example

> **Important Note**: This is an illustrative example with generic values and concepts. Concept names, percentages, and specific calculations **must be configured by the implementer** according to the laws and policies of their jurisdiction. The engine **does not include predefined legal rules**.

```
Base Salary:               $ 10,000.00
+ Earning A:               $    500.00
+ Earning B:               $    300.00
= GROSS SALARY:            $ 10,800.00

- Deduction A (X%):        $    756.00
- Deduction B (Y%):        $    540.00
- Deduction C:             $    200.00
= NET SALARY:              $  9,304.00

Employer Benefits (Company Costs):
+ Benefit A (W%):          $  2,160.00
+ Benefit B (Z%):          $    216.00
+ Benefit C (P%):          $    899.64
+ Benefit D (P%):          $    899.64
+ Benefit E (P%):          $    899.64
= TOTAL COMPANY COST:      $ 15,178.92
```

**How to configure these concepts?**

All concepts, percentages, and calculation rules are defined through:
- **Configurable earnings**: Define any type of additional income
- **Priority-based deductions**: Configure the order and formula for each deduction
- **Employer benefits**: Configure contributions according to your jurisdiction
- **Calculation rules**: Use the rule engine to implement complex logic (brackets, caps, exemptions, etc.)

See the [complete documentation](docs/) to learn how to configure your payroll system.

## Development

### Install development dependencies

```bash
pip install -r development.txt
```

### Database Structure

The main models are:

**System Configuration:**
- `Usuario`: System users with roles (Admin, HR, Audit)
- `Empresa`: Companies or entities that hire employees
- `Moneda`: System currencies
- `TipoCambio`: Exchange rates between currencies
- `ConfiguracionGlobal`: Global system configuration

**Personnel Management:**
- `Empleado`: Employee master record
- `CampoPersonalizado`: Custom fields for employees
- `HistorialSalario`: Salary change history

**Payroll:**
- `Percepcion`: Income concepts
- `Deduccion`: Deduction concepts
- `Prestacion`: Employer contributions
- `ReglaCalculo`: Calculation rules with configurable schemas
- `TipoPlanilla`: Payroll types (monthly, biweekly, etc.)
- `Planilla`: Payroll configuration
- `Nomina`: Payroll execution
- `NominaEmpleado`: Payroll detail per employee
- `NominaDetalle`: Detail lines (earnings, deductions)
- `NominaNovedad`: Payroll novelties
- `ComprobanteContable`: Accounting vouchers

**Loans:**
- `Adelanto`: Employee loans and advances
- `AdelantoAbono`: Loan payments

**Vacations:**
- `VacationPolicy`: Configurable vacation policies
- `VacationAccount`: Vacation accounts per employee
- `VacationLedger`: Vacation ledger (audit)
- `VacationNovelty`: Vacation requests and novelties
- `ConfiguracionVacaciones`: Vacation configuration (legacy)
- `VacacionEmpleado`: Employee vacations (legacy)
- `PrestacionAcumulada`: Accumulated benefits
- `CargaInicialPrestacion`: Initial benefit load

**Reports:**
- `Report`: Custom report definitions
- `ReportRole`: Report permissions by role
- `ReportExecution`: Report execution history
- `ReportAudit`: Report audit

## Social Contract and Responsibilities

This project is governed by a [Social Contract](SOCIAL_CONTRACT.md) that clearly establishes:

### Project Scope

- **Jurisdiction-agnostic engine**: Does not include and will not include hardcoded legal rules
- **Strict separation**: Between calculation engine, rule configuration, and payroll orchestration
- **Predictable and reproducible calculation**: Calculations are deterministic and auditable
- **Extensible by configuration**: Any legal change is implemented through configuration, not code

### Default Functionality

The engine, by default, **only** calculates:
1. Employee base salary according to the defined period
2. Salary advance installments when they exist

All other concepts (earnings, deductions, benefits, taxes, caps, brackets, exemptions) exist only if the implementer configures them.

### Implementer Responsibility

Correct use of the engine requires that the implementer:
- Has knowledge of how payroll is calculated in their jurisdiction
- Understands the applicable legal framework
- Is capable of manually calculating a complete payroll
- Compares manual results with system results
- Identifies and corrects configuration errors

### Warranties and Limitations

This software is distributed under the Apache 2.0 License **"AS IS"**:
- ✅ **Promises**: Predictable, reproducible, and auditable calculations
- ✅ **Promises**: Remain jurisdiction-agnostic
- ✅ **Promises**: Separation between engine and configuration
- ❌ **Does not guarantee**: Regulatory compliance in any jurisdiction
- ❌ **Does not guarantee**: Correct results without appropriate configuration
- ❌ **Does not replace**: Professional knowledge or legal advice

**For more details, read the complete [Social Contract](SOCIAL_CONTRACT.md) before using this system in production.**

## Support

To report issues or request features, please open an [Issue on GitHub](https://github.com/williamjmorenor/coati-payroll/issues).

## License
```
SPDX-License-Identifier: Apache-2.0
Copyright 2025 - 2026 BMO Soluciones, S.A.
```

This project is licensed under the **Apache License 2.0** - a permissive open-source license that allows free use, modification, and distribution (including for commercial purposes), as long as copyright and license notices are preserved. It also includes a patent grant to protect users from patent claims but terminates rights if you file such claims. You may combine Apache-licensed code with proprietary software, but you cannot use Apache trademarks or logos without permission, and you must provide proper attribution to the original authors.

For more details, see the [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a branch for your feature (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

---

Made with ❤️ by [BMO Soluciones, S.A.](https://github.com/williamjmorenor)
