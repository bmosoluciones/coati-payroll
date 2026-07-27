# Database Compatibility Guide

Coati Payroll is designed to work seamlessly with multiple database engines. This guide explains how the application maintains database agnosticism and how to configure different database backends.

## Supported Database Engines

The application officially supports three database engines:

- **SQLite** - Default for development and testing
- **PostgreSQL** - Recommended for production
- **MySQL/MariaDB** - Alternative for production

## Database-Agnostic Design

### Schema Design Principles

The application follows these principles to ensure compatibility:

1. **Standard SQLAlchemy ORM**: All database operations use SQLAlchemy's ORM, avoiding raw SQL queries
2. **Standard Column Types**: Uses database-agnostic column types that SQLAlchemy translates appropriately
3. **Modern Query API**: Uses SQLAlchemy 2.0 style queries with `select()` instead of deprecated `session.query()`
4. **Portable Primary Keys**: Uses ULID-based String(26) primary keys instead of database-specific auto-increment
5. **JSON Storage**: Uses SQLAlchemy's `JSON` type which works across all supported databases
6. **Decimal Precision**: Uses `Numeric` type for monetary values to ensure consistent precision

### Key Compatibility Features

#### 1. Primary Keys (ULID)

Instead of auto-incrementing integers, we use ULID (Universally Unique Lexicographically Sortable Identifier):

```python
id = database.Column(
    database.String(26),
    primary_key=True,
    nullable=False,
    index=True,
    default=generador_de_codigos_unicos,
)
```

**Benefits:**
- Works identically across all databases
- No dependency on database-specific sequences
- Sortable by creation time
- Globally unique without coordination

#### 2. JSON Columns

We use SQLAlchemy's `MutableDict.as_mutable(JSON)` for flexible data storage:

```python
datos_adicionales = database.Column(
    MutableDict.as_mutable(JSON), 
    nullable=True, 
    default=dict
)
```

**How it works:**
- SQLite: Stores as TEXT and deserializes automatically
- PostgreSQL: Uses native JSONB for better performance
- MySQL: Uses JSON column type (MySQL 5.7+)

#### 3. Decimal/Numeric Types

For monetary values, we use `Numeric` with specific precision:

```python
salario_base = database.Column(
    database.Numeric(14, 2),
    nullable=False,
    default=Decimal("0.00")
)
```

**Ensures:**
- Exact decimal arithmetic (no floating-point errors)
- Consistent precision across databases
- Proper currency calculations

#### 4. Date and DateTime Handling

We use timezone-aware UTC datetimes:

```python
def utc_now() -> datetime:
    """Generate timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

timestamp = database.Column(database.DateTime, default=utc_now, nullable=False)
```

**Benefits:**
- Consistent across timezones
- No ambiguity with DST changes
- Portable across databases

#### 5. Boolean Types

Standard boolean columns work across all databases:

```python
activo = database.Column(database.Boolean(), default=True)
```

**Translation:**
- SQLite: INTEGER (0 or 1)
- PostgreSQL: BOOLEAN
- MySQL: TINYINT(1)

#### 6. Modern Query Syntax

We use SQLAlchemy 2.0 style queries:

```python
# ✅ Good: Modern select() syntax
from sqlalchemy import select, func

count = db.session.execute(
    select(func.count()).select_from(Empleado)
).scalar()

# ❌ Avoid: Deprecated query() syntax
count = db.session.query(Empleado).count()
```

## Database Configuration

### SQLite (Development)

SQLite is the default for development and testing. No additional setup required.

```bash
# Uses in-memory database for tests
export TESTING=1
python -m pytest

# Uses file-based database for development
python app.py
```

**Configuration:**
- Database file: `coati_payroll.db` (in project root)
- No server required
- Automatic schema creation

### PostgreSQL (Production - Recommended)

PostgreSQL offers the best performance and features for production use.

#### Installation

```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql
```

#### Setup

```bash
# Create database
sudo -u postgres createdb coati_payroll

# Create user
sudo -u postgres createuser -P coati_user
```

#### Configuration

Set the `DATABASE_URL` environment variable:

```bash
# Standard format
export DATABASE_URL="postgresql://coati_user:password@localhost/coati_payroll"

# With pg8000 driver (auto-detected)
export DATABASE_URL="postgresql://coati_user:password@localhost/coati_payroll"

# Application automatically converts to: postgresql+pg8000://...
```

#### Required Python Package

The application automatically uses `pg8000` driver (already in requirements.txt):

```txt
pg8000
```

### MySQL/MariaDB (Production - Alternative)

MySQL 5.7+ or MariaDB 10.2+ are supported.

#### Installation

```bash
# Ubuntu/Debian
sudo apt-get install mysql-server

# macOS
brew install mysql

# Or MariaDB
brew install mariadb
```

#### Setup

```bash
# Create database
mysql -u root -p -e "CREATE DATABASE coati_payroll CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Create user
mysql -u root -p -e "CREATE USER 'coati_user'@'localhost' IDENTIFIED BY 'password';"
mysql -u root -p -e "GRANT ALL PRIVILEGES ON coati_payroll.* TO 'coati_user'@'localhost';"
```

#### Configuration

Set the `DATABASE_URL` environment variable:

```bash
# MySQL
export DATABASE_URL="mysql://coati_user:password@localhost/coati_payroll"

# Application automatically converts to: mysql+mysqlconnector://...

# MariaDB
export DATABASE_URL="mariadb://coati_user:password@localhost/coati_payroll"

# Application automatically converts to: mariadb+mariadbconnector://...
```

#### Required Python Package

The application uses appropriate drivers (already in requirements.txt):

```txt
mysql-connector-python  # For MySQL
```

## Connection String Auto-Correction

The application automatically corrects database URLs to use the appropriate drivers:

| Input Prefix | Auto-Corrected To | Driver Used |
|-------------|------------------|-------------|
| `postgres://` | `postgresql+pg8000://` | pg8000 |
| `postgresql://` | `postgresql+pg8000://` | pg8000 |
| `mysql://` | `mysql+mysqlconnector://` | mysql-connector-python |
| `mariadb://` | `mariadb+mariadbconnector://` | MariaDB Connector |
| `sqlite://` | (unchanged) | sqlite3 |

This happens automatically in `config.py` so you can use simple connection strings.

## Testing Database Compatibility

The test suite includes comprehensive database compatibility tests in `tests/test_database_compatibility.py`:

```bash
# Run database compatibility tests
python -m pytest tests/test_database_compatibility.py -v
```

Tests verify:
- ✅ ULID primary keys
- ✅ Numeric/Decimal precision
- ✅ JSON column storage and retrieval
- ✅ Unique constraints (single and composite)
- ✅ Foreign key relationships
- ✅ Date and DateTime handling
- ✅ Boolean columns
- ✅ Count queries with modern syntax
- ✅ ORDER BY queries
- ✅ Date range filtering

## Migration Between Databases

If you need to migrate data between databases:

### Option 1: SQL Dump (Recommended)

**PostgreSQL:**
```bash
# Export
pg_dump coati_payroll > backup.sql

# Import to new database
psql new_coati_payroll < backup.sql
```

**MySQL:**
```bash
# Export
mysqldump coati_payroll > backup.sql

# Import to new database
mysql new_coati_payroll < backup.sql
```

### Option 2: Python Script

For cross-database migrations (e.g., SQLite to PostgreSQL):

```python
# Copy data using Python
from coati_payroll import create_app
from coati_payroll.model import db, Moneda, Empleado  # etc.

# Connect to source
app_source = create_app()
app_source.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///old.db'

# Connect to target
app_target = create_app()
app_target.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://...'

# Copy data (simplified example)
with app_source.app_context():
    monedas = Moneda.query.all()
    
with app_target.app_context():
    db.session.add_all(monedas)
    db.session.commit()
```

## Performance Considerations

### SQLite
- **Best for:** Development, testing, small deployments
- **Limits:** Single writer, file-based, no horizontal scaling
- **Max recommended:** ~100 employees

### PostgreSQL
- **Best for:** Production, high concurrency, complex queries
- **Features:** JSONB indexing, full-text search, extensive extensions
- **Scalability:** Horizontal scaling with replication

### MySQL
- **Best for:** Production, web applications, good compatibility
- **Features:** Good performance, wide hosting support
- **Scalability:** Read replicas, clustering options

## Common Issues and Solutions

### Issue: JSON columns not working in MySQL

**Solution:** Ensure MySQL 5.7+ which has native JSON support.

```bash
mysql --version  # Check version
```

### Issue: Decimal precision differences

**Solution:** Always use `Decimal` type in Python, never `float`:

```python
from decimal import Decimal

# ✅ Correct
salario = Decimal("15750.50")

# ❌ Wrong
salario = 15750.50
```

### Issue: Date/Time timezone issues

**Solution:** Always use UTC timezone-aware datetimes:

```python
from datetime import datetime, timezone

# ✅ Correct
now = datetime.now(timezone.utc)

# ❌ Wrong (deprecated)
now = datetime.utcnow()
```

### Issue: Unique constraint violations during tests

**Solution:** Ensure test isolation with unique data or proper cleanup:

```python
@pytest.fixture(autouse=True)
def cleanup_database(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield
    with app.app_context():
        db.drop_all()
```

## Best Practices

1. **Always use ORM queries** - Avoid raw SQL
2. **Use SQLAlchemy 2.0 syntax** - Modern `select()` instead of `query()`
3. **Test with target database** - Don't just test on SQLite if deploying to PostgreSQL
4. **Use transactions** - Ensure data consistency with proper transaction handling
5. **Index appropriately** - Add indexes for frequently queried columns
6. **Monitor performance** - Use database-specific tools to identify slow queries

## Troubleshooting

### Enable SQLAlchemy Query Logging

```python
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Check Connection String

```python
from coati_payroll.config import CONFIGURACION
print(CONFIGURACION['SQLALCHEMY_DATABASE_URI'])
```

### Verify Database Schema

```bash
# PostgreSQL
psql coati_payroll -c "\dt"

# MySQL
mysql -u coati_user -p coati_payroll -e "SHOW TABLES;"

# SQLite
sqlite3 coati_payroll.db ".tables"
```

## Additional Resources

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
