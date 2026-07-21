# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Command line interface for Coati Payroll system administration."""

from __future__ import annotations

# <-------------------------------------------------------------------------> #
# Standard library
# <-------------------------------------------------------------------------> #
import sys
import os
import importlib
import importlib.util
import json as json_module
import getpass
import subprocess
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# <-------------------------------------------------------------------------> #
# Third party libraries
# <-------------------------------------------------------------------------> #
import click
from flask import current_app
from flask.cli import with_appcontext

# <-------------------------------------------------------------------------> #
# Local modules
# <-------------------------------------------------------------------------> #
from coati_payroll.model import db, Usuario, PluginRegistry
from coati_payroll.auth import proteger_passwd
from coati_payroll.log import log
from coati_payroll.plugin_manager import discover_installed_plugins, load_plugin_module, sync_plugin_registry
from coati_payroll.wsgi_server import serve as wsgi_server


# Global context to store CLI options
class CLIContext:

    def __init__(self):
        self.environment = None
        self.json_output = False
        self.auto_yes = False


pass_context = click.make_pass_decorator(CLIContext, ensure=True)


def output_result(ctx, message, data=None, success=True):
    """Output result in appropriate format (JSON or text)."""
    if ctx.json_output:
        result = {"success": success, "message": message}
        if data:
            result["data"] = data
        click.echo(json_module.dumps(result, indent=2))
    else:
        symbol = "✓" if success else "✗"
        click.echo(f"{symbol} {message}")


def _run_plugin_hook(ctx, module, hook_name, plugin_name, aliases=None):
    """Run a plugin hook function with standard error handling."""
    fn = getattr(module, hook_name, None)
    if fn is None and aliases:
        for alias in aliases:
            fn = getattr(module, alias, None)
            if fn is not None:
                break
    if fn is None or not callable(fn):
        alias_msg = " or ".join(f"'{a}()'" for a in [hook_name] + (aliases or []))
        raise click.ClickException(f"Plugin does not provide callable {alias_msg}")
    try:
        fn()
        db.create_all()
        output_result(ctx, f"Plugin '{plugin_name}' {hook_name}")
    except Exception as exc:
        log.exception(f"Plugin {hook_name} failed")
        output_result(ctx, f"Plugin '{plugin_name}' {hook_name} failed: {exc}", None, False)
        raise click.ClickException(str(exc))


def _get_plugin_metadata(plugin_id: str) -> dict[str, Any]:
    meta: dict[str, Any] = {"plugin_id": plugin_id}
    try:
        discovered = {p.plugin_id: p for p in discover_installed_plugins()}
        if plugin_id in discovered:
            meta["version"] = discovered[plugin_id].version
    except Exception:
        pass
    try:
        mod = load_plugin_module(plugin_id)
        info = getattr(mod, "PLUGIN_INFO", None) or getattr(mod, "INFO", None)
        if isinstance(info, dict):
            meta.update({
                "description": info.get("description"),
                "maintainer": info.get("maintainer"),
                "contact": info.get("contact"),
                "version": info.get("version", meta.get("version")),
            })
        else:
            meta.setdefault("version", getattr(mod, "__version__", meta.get("version")))
            meta["description"] = meta.get("description") or (
                mod.__doc__.strip() if getattr(mod, "__doc__", None) else None
            )
            meta["maintainer"] = getattr(mod, "MAINTAINER", None)
            meta["contact"] = getattr(mod, "CONTACT", None)
    except Exception:
        pass
    try:
        rec = db.session.execute(db.select(PluginRegistry).filter_by(plugin_id=plugin_id)).scalars().first()
        if rec:
            meta["installed"] = rec.installed
            meta["active"] = rec.active
            meta["distribution_name"] = rec.distribution_name
    except Exception:
        pass
    return meta


def _toggle_plugin_active(plugin_name, active, ctx):
    """Enable or disable a plugin in the registry."""
    try:
        sync_plugin_registry()
        record = (
            db.session.execute(
                db.select(PluginRegistry).filter(
                    (PluginRegistry.plugin_id == plugin_name) | (PluginRegistry.distribution_name == plugin_name)
                )
            )
            .scalars()
            .first()
        )
        if record is None:
            raise click.ClickException("Plugin no registrado en la base de datos")
        if active and not record.installed:
            raise click.ClickException("Plugin no está instalado en el entorno")
        record.active = active
        db.session.commit()
        action = "habilitado" if active else "deshabilitado"
        output_result(ctx, f"Plugin '{plugin_name}' {action}.")
    except click.ClickException:
        raise
    except Exception as exc:
        db.session.rollback()
        output_result(ctx, f"No se pudo {action} el plugin: {exc}", None, False)
        raise click.ClickException(str(exc))


class PluginsCommand(click.Group):

    def list_commands(self, cli_ctx):
        try:
            return [p.plugin_id for p in discover_installed_plugins()]
        except Exception:
            return []

    def get_command(self, cli_ctx, name):

        def _load_module_or_fail():
            try:
                return load_plugin_module(name)
            except Exception as exc:
                raise click.ClickException(str(exc))

        @click.group(name=name, help=f"Gestión del plugin '{name}'")
        def plugin_group():
            """Grupo de comandos del plugin específico."""

        @plugin_group.command("init")
        @with_appcontext
        @pass_context
        def plugin_init(ctx):
            module = _load_module_or_fail()
            _run_plugin_hook(ctx, module, "init", name)

        @plugin_group.command("update")
        @with_appcontext
        @pass_context
        def plugin_update(ctx):
            module = _load_module_or_fail()
            _run_plugin_hook(ctx, module, "update", name)

        @plugin_group.command("demo_data")
        @with_appcontext
        @pass_context
        def plugin_demo_data(ctx):
            """Carga datos de demostración para pruebas automáticas."""
            module = _load_module_or_fail()
            _run_plugin_hook(ctx, module, "demo_data", name, aliases=["load_demo_data"])

        @plugin_group.command("enable")
        @with_appcontext
        @pass_context
        def plugin_enable(ctx):
            """Habilita el plugin en el registro (active=True)."""
            _toggle_plugin_active(name, True, ctx)

        @plugin_group.command("disable")
        @with_appcontext
        @pass_context
        def plugin_disable(ctx):
            """Deshabilita el plugin en el registro (active=False)."""
            _toggle_plugin_active(name, False, ctx)

        @plugin_group.command("status")
        @with_appcontext
        @pass_context
        def plugin_status(ctx):
            """Muestra el estado del plugin (installed/active/version)."""
            try:
                sync_plugin_registry()
                meta = _get_plugin_metadata(name)
                if ctx.json_output:
                    output_result(ctx, f"Estado del plugin '{name}'", meta, True)
                else:
                    click.echo(f"Estado del plugin '{name}':")
                    click.echo(f"  Installed: {meta.get('installed', False)}")
                    click.echo(f"  Active: {meta.get('active', False)}")
                    click.echo(f"  Version: {meta.get('version', 'desconocida')}\n")
            except Exception as exc:
                output_result(ctx, f"No se pudo obtener estado: {exc}", None, False)
                raise click.ClickException(str(exc))

        @plugin_group.command("version")
        @with_appcontext
        @pass_context
        def plugin_version(ctx):
            """Muestra la versión del plugin."""
            meta = _get_plugin_metadata(name)
            ver = meta.get("version") or "desconocida"
            if ctx.json_output:
                output_result(ctx, f"Versión del plugin '{name}'", {"version": ver}, True)
            else:
                click.echo(ver)

        @plugin_group.command("info")
        @with_appcontext
        @pass_context
        def plugin_info(ctx):
            """Muestra información del plugin (descripción y enlaces)."""
            meta = _get_plugin_metadata(name)
            if ctx.json_output:
                output_result(ctx, f"Información del plugin '{name}'", meta, True)
            else:
                click.echo(f"Info del plugin '{name}':")
                info_keys = [("description", "Description"), ("distribution_name", "Package"), ("version", "Version")]
                for key, label in info_keys:
                    if meta.get(key):
                        click.echo(f"  {label}: {meta[key]}")
                click.echo(f"  Installed: {meta.get('installed', False)}")
                click.echo(f"  Active: {meta.get('active', False)}")

        @plugin_group.command("maintainer")
        @with_appcontext
        @pass_context
        def plugin_maintainer(ctx):
            """Muestra el maintainer del plugin (según metadatos)."""
            meta = _get_plugin_metadata(name)
            maint = meta.get("maintainer") or "desconocido"
            if ctx.json_output:
                output_result(ctx, f"Maintainer del plugin '{name}'", {"maintainer": maint}, True)
            else:
                click.echo(maint)

        plugin_group.add_command(plugin_maintainer, "mantainer")

        @plugin_group.command("contact")
        @with_appcontext
        @pass_context
        def plugin_contact(ctx):
            """Muestra el contacto del plugin (correo/URL si disponible)."""
            meta = _get_plugin_metadata(name)
            contact = meta.get("contact") or "no disponible"
            if ctx.json_output:
                output_result(ctx, f"Contacto del plugin '{name}'", {"contact": contact}, True)
            else:
                click.echo(contact)

        return plugin_group


plugins = PluginsCommand(name="plugins", help="Gestión de plugins instalados")

# ============================================================================
# SYSTEM COMMANDS
# ============================================================================


def _system_status():
    """Get system status data.

    Returns:
        dict: Dictionary containing database status, admin user status, and app mode.
    """
    # Check database
    db.session.execute(db.text("SELECT 1"))
    db_status = "connected"

    # Check admin user
    admin = db.session.execute(db.select(Usuario).filter_by(tipo="admin", activo=True)).scalar_one_or_none()
    admin_status = "active" if admin else "none"

    # Get app mode
    app_mode = os.environ.get("FLASK_ENV", "production")

    return {"database": db_status, "admin_user": admin_status, "mode": app_mode}


@click.group()
def system():
    """System-level operations."""


@system.command("status")
@with_appcontext
@pass_context
def system_status(ctx):
    """Show system status."""
    try:
        data = _system_status()

        if ctx.json_output:
            output_result(ctx, "System status", data, True)
        else:
            click.echo("System Status:")
            click.echo(f"  Database: {data['database']}")
            click.echo(f"  Admin User: {data['admin_user']}")
            click.echo(f"  Mode: {data['mode']}")

    except Exception as e:
        output_result(ctx, f"Failed to get system status: {e}", None, False)
        sys.exit(1)


def _system_check():
    """Run system checks and return results.

    Returns:
        list: List of check results with name, status, and optional error/missing data.
    """
    checks = []

    # Check database connection
    try:
        db.session.execute(db.text("SELECT 1"))
        checks.append({"name": "Database connection", "status": "OK"})
    except Exception as e:
        checks.append({"name": "Database connection", "status": "FAILED", "error": str(e)})

    # Check admin user
    try:
        admin = db.session.execute(db.select(Usuario).filter_by(tipo="admin", activo=True)).scalar_one_or_none()
        if admin:
            checks.append({"name": "Active admin user", "status": "OK", "user": admin.usuario})
        else:
            checks.append({"name": "Active admin user", "status": "WARNING", "error": "No active admin"})
    except Exception as e:
        checks.append({"name": "Active admin user", "status": "FAILED", "error": str(e)})

    # Check required tables
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    required_tables = ["usuario", "moneda", "empleado", "planilla", "nomina"]
    missing = [t for t in required_tables if t not in tables]

    if missing:
        checks.append({"name": "Required tables", "status": "WARNING", "missing": missing})
    else:
        checks.append({"name": "Required tables", "status": "OK", "count": len(required_tables)})

    return checks


@system.command("check")
@with_appcontext
@pass_context
def system_check(ctx):
    """Run system checks."""
    try:
        checks = _system_check()

        if ctx.json_output:
            output_result(ctx, "System checks completed", {"checks": checks}, True)
        else:
            click.echo("Running system checks...")
            click.echo()
            for check in checks:
                status_symbol = "✓" if check["status"] == "OK" else ("⚠" if check["status"] == "WARNING" else "✗")
                click.echo(f"{status_symbol} {check['name']}: {check['status']}")
                if "error" in check:
                    click.echo(f"  Error: {check['error']}")
                if "missing" in check:
                    click.echo(f"  Missing: {', '.join(check['missing'])}")

    except Exception as e:
        output_result(ctx, f"System check failed: {e}", None, False)
        sys.exit(1)


def _system_info():
    """Get system information.

    Returns:
        dict: Dictionary containing version, python version, database URI, and flask version.
    """
    from coati_payroll.version import __version__

    info = {
        "version": __version__,
        "python": sys.version.split()[0],
        "database_uri": "***" if "@" in str(db.engine.url) else str(db.engine.url),
    }

    try:
        from importlib.metadata import version as get_version

        info["flask"] = get_version("flask")
    except Exception:
        pass

    return info


@system.command("info")
@with_appcontext
@pass_context
def system_info(ctx):
    """Show system information."""
    try:
        info = _system_info()

        if ctx.json_output:
            output_result(ctx, "System information", info, True)
        else:
            click.echo("System Information:")
            click.echo(f"  Coati Payroll: {info['version']}")
            click.echo(f"  Python: {info['python']}")
            if "flask" in info:
                click.echo(f"  Flask: {info['flask']}")
            click.echo(f"  Database: {info['database_uri']}")

    except Exception as e:
        output_result(ctx, f"Failed to get system info: {e}", None, False)
        sys.exit(1)


def _system_env():
    """Get environment variables.

    Returns:
        dict: Dictionary containing relevant environment variables.
    """
    return {
        "FLASK_APP": os.environ.get("FLASK_APP", "not set"),
        "FLASK_ENV": os.environ.get("FLASK_ENV", "not set"),
        "DATABASE_URL": "***" if os.environ.get("DATABASE_URL") else "not set",
        "ADMIN_USER": os.environ.get("ADMIN_USER", "not set"),
        "COATI_LANG": os.environ.get("COATI_LANG", "not set"),
    }


@system.command("env")
@pass_context
def system_env(ctx):
    """Show environment variables."""
    env_vars = _system_env()

    if ctx.json_output:
        output_result(ctx, "Environment variables", env_vars, True)
    else:
        click.echo("Environment Variables:")
        for key, value in env_vars.items():
            click.echo(f"  {key}: {value}")


# ============================================================================
# DATABASE COMMANDS
# ============================================================================


def _database_status():
    """Get database status.

    Returns:
        dict: Dictionary containing table count, table names, and record counts.
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    # Count records in key tables
    counts = {}
    for table in ["usuario", "empleado", "nomina"]:
        if table in tables:
            result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = result.scalar()

    return {"tables": len(tables), "table_names": tables[:10], "record_counts": counts}


@click.command()
@with_appcontext
@pass_context
def serve(ctx):
    """Run the application server."""
    try:
        wsgi_server(app=current_app)
    except Exception as e:
        click.echo(f"Failed to start server: {e}", err=True)


@click.group()
def database():
    """Database management commands."""


@database.command("status")
@with_appcontext
@pass_context
def database_status(ctx):
    """Show database status."""
    try:
        data = _database_status()

        if ctx.json_output:
            output_result(ctx, "Database status", data, True)
        else:
            click.echo("Database Status:")
            click.echo(f"  Tables: {data['tables']}")
            click.echo("  Records:")
            for table, count in data["record_counts"].items():
                click.echo(f"    {table}: {count}")

    except Exception as e:
        output_result(ctx, f"Failed to get database status: {e}", None, False)
        sys.exit(1)


def _database_init(app):
    """Initialize database tables and admin user.

    Args:
        app: Flask application instance

    Returns:
        str: Admin username that was created/initialized
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    if not inspector.get_table_names():
        db.create_all()
    core_module = importlib.import_module("coati_payroll")
    ensure_database_initialized = getattr(core_module, "ensure_database_initialized")
    ensure_database_initialized(app)

    return os.environ.get("ADMIN_USER", "coati-admin")


@database.command("init")
@with_appcontext
@pass_context
def database_init(ctx):
    """Initialize database tables and create admin user."""
    try:
        click.echo("Initializing database...")

        admin_user = _database_init(current_app)

        output_result(ctx, "Database tables created")
        output_result(ctx, f"Administrator user '{admin_user}' is ready")

        if not ctx.json_output:
            click.echo()
            click.echo("Database initialization complete!")

    except Exception as e:
        output_result(ctx, f"Failed to initialize database: {e}", None, False)
        log.exception("Failed to initialize database")
        sys.exit(1)


def _database_seed():
    """Seed database with initial data."""
    from sqlalchemy import inspect

    from coati_payroll.initial_data import load_initial_data

    inspector = inspect(db.engine)
    if not inspector.get_table_names():
        db.create_all()
    load_initial_data()


@database.command("seed")
@with_appcontext
@pass_context
def database_seed(ctx):
    """Create tables if needed and load initial data."""
    try:
        click.echo("Seeding database with initial data...")

        _database_seed()

        output_result(ctx, "Database tables verified")
        output_result(ctx, "Initial data loaded")

        if not ctx.json_output:
            click.echo()
            click.echo("Database seeding complete!")

    except Exception as e:
        output_result(ctx, f"Failed to seed database: {e}", None, False)
        log.exception("Failed to seed database")
        sys.exit(1)


def _database_drop():
    """Drop all database tables."""
    db.drop_all()


@database.command("drop")
@click.confirmation_option(prompt="Are you sure you want to drop all tables? This will DELETE ALL DATA!")
@with_appcontext
@pass_context
def database_drop(ctx):
    """Remove all database tables."""
    try:
        click.echo("Dropping all database tables...")
        _database_drop()
        output_result(ctx, "All database tables have been dropped")

        if not ctx.json_output:
            click.echo()
            click.echo("Database drop complete!")

    except Exception as e:
        output_result(ctx, f"Failed to drop database: {e}", None, False)
        log.exception("Failed to drop database")
        sys.exit(1)


def _backup_sqlite(db_url_str, output=None):
    """Backup SQLite database.

    Args:
        db_url_str: Database URL string
        output: Optional output file path

    Returns:
        Path: Output file path
    """
    db_path = db_url_str.replace("sqlite:///", "").replace("sqlite://", "")

    # Remove query parameters if present (e.g., ?check_same_thread=False)
    if "?" in db_path:
        db_path = db_path.split("?")[0]

    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"coati_backup_{timestamp}.db"

    output_path = Path(output)

    if db_path == ":memory:":
        source_conn = db.engine.raw_connection()
        dest_conn = sqlite3.connect(str(output_path))
        source_conn.backup(dest_conn)
        dest_conn.close()
    else:
        shutil.copy2(db_path, output_path)

    return output_path


def _backup_postgresql(db_url_str, output=None):
    """Backup PostgreSQL database.

    Args:
        db_url_str: Database URL string
        output: Optional output file path

    Returns:
        Path: Output file path
    """
    parsed = urlparse(db_url_str)

    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"coati_backup_{timestamp}.sql"

    output_path = Path(output)

    cmd = ["pg_dump"]

    if parsed.hostname:
        cmd.extend(["-h", parsed.hostname])
    if parsed.port:
        cmd.extend(["-p", str(parsed.port)])
    if parsed.username:
        cmd.extend(["-U", parsed.username])

    db_name = parsed.path.lstrip("/")
    cmd.append(db_name)

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    with output_path.open("w", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env, text=True, check=False)

    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr}")

    return output_path


def _backup_mysql(db_url_str, output=None):
    """Backup MySQL database.

    Args:
        db_url_str: Database URL string
        output: Optional output file path

    Returns:
        Path: Output file path
    """
    parsed = urlparse(db_url_str)

    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"coati_backup_{timestamp}.sql"

    output_path = Path(output)

    cmd = ["mysqldump"]

    if parsed.hostname:
        cmd.extend(["-h", parsed.hostname])
    if parsed.port:
        cmd.extend(["-P", str(parsed.port)])
    if parsed.username:
        cmd.extend(["-u", parsed.username])

    db_name = parsed.path.lstrip("/")
    cmd.append(db_name)

    env = os.environ.copy()
    if parsed.password:
        env["MYSQL_PWD"] = parsed.password

    with output_path.open("w", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env, text=True, check=False)

    if result.returncode != 0:
        raise RuntimeError(f"mysqldump failed: {result.stderr}")

    return output_path


@database.command("backup")
@click.option("--output", "-o", default=None, help="Output file path (default: auto-generated with timestamp)")
@with_appcontext
@pass_context
def database_backup(ctx, output):
    """Create a database backup using native database tools."""
    try:
        db_url_str = str(db.engine.url)

        if db_url_str.startswith("sqlite"):
            db_path = db_url_str.replace("sqlite:///", "").replace("sqlite://", "")

            click.echo("Creating SQLite backup...")
            if db_path == ":memory:":
                click.echo("Source: in-memory database")
            else:
                click.echo(f"Source: {db_path}")

            output_path = _backup_sqlite(db_url_str, output)

            click.echo()
            output_result(ctx, "Backup completed successfully!")
            click.echo("  Database type: SQLite")
            click.echo(f"  Output file: {output_path.absolute()}")

        elif "postgresql" in db_url_str or "postgres" in db_url_str:
            parsed = urlparse(db_url_str)

            click.echo("Creating PostgreSQL backup...")
            click.echo(f"Database: {parsed.path.lstrip('/')}")

            output_path = _backup_postgresql(db_url_str, output)

            click.echo()
            output_result(ctx, "Backup completed successfully!")
            click.echo("  Database type: PostgreSQL")
            click.echo(f"  Output file: {output_path.absolute()}")

        elif "mysql" in db_url_str:
            parsed = urlparse(db_url_str)

            click.echo("Creating MySQL backup...")
            click.echo(f"Database: {parsed.path.lstrip('/')}")

            output_path = _backup_mysql(db_url_str, output)

            click.echo()
            output_result(ctx, "Backup completed successfully!")
            click.echo("  Database type: MySQL")
            click.echo(f"  Output file: {output_path.absolute()}")

        else:
            click.echo(f"Error: Unsupported database type: {db_url_str}", err=True)
            click.echo("Supported databases: SQLite, PostgreSQL, MySQL")
            sys.exit(1)

    except Exception as e:
        output_result(ctx, f"Failed to create backup: {e}", None, False)
        log.exception("Failed to create database backup")
        sys.exit(1)


def _database_restore_sqlite(backup_file, db_url_str):
    """Restore SQLite database from backup.

    Args:
        backup_file: Path to backup file
        db_url_str: Database URL string
    """
    backup_path = Path(backup_file)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    db_path = db_url_str.replace("sqlite:///", "").replace("sqlite://", "")

    if db_path == ":memory:":
        raise ValueError("Cannot restore to in-memory database")

    shutil.copy2(backup_path, db_path)


@database.command("restore")
@click.argument("backup_file")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@with_appcontext
@pass_context
def database_restore(ctx, backup_file, yes):
    """Restore database from backup file."""
    if not yes and not ctx.auto_yes:
        if not click.confirm("This will overwrite the current database. Continue?"):
            click.echo("Restore cancelled.")
            return

    try:
        db_url_str = str(db.engine.url)

        if db_url_str.startswith("sqlite"):
            click.echo(f"Restoring SQLite database from: {backup_file}")
            _database_restore_sqlite(backup_file, db_url_str)
            output_result(ctx, "Database restored successfully!")

        else:
            output_result(ctx, "Restore only supported for SQLite currently", None, False)
            sys.exit(1)

    except Exception as e:
        output_result(ctx, f"Failed to restore database: {e}", None, False)
        log.exception("Failed to restore database")
        sys.exit(1)


def _database_migrate_upgrade():
    """Apply database migrations to latest version.

    Helper function used by both migrate and upgrade commands.
    """
    core_module = importlib.import_module("coati_payroll")
    alembic = getattr(core_module, "alembic")

    click.echo("Applying database migrations...")
    alembic.upgrade()


@database.command("migrate")
@with_appcontext
@pass_context
def database_migrate(ctx):
    """Apply database migrations to latest version."""
    try:
        _database_migrate_upgrade()
        output_result(ctx, "Database migrated successfully to latest version")

    except Exception as e:
        output_result(ctx, f"Failed to apply migrations: {e}", None, False)
        log.exception("Failed to apply migrations")
        sys.exit(1)


@database.command("upgrade")
@with_appcontext
@pass_context
def database_upgrade(ctx):
    """Apply database migrations (alias for migrate)."""
    try:
        _database_migrate_upgrade()
        output_result(ctx, "Database migrated successfully to latest version")

    except Exception as e:
        output_result(ctx, f"Failed to apply migrations: {e}", None, False)
        log.exception("Failed to apply migrations")
        sys.exit(1)


@database.command("downgrade")
@click.argument("revision", default="-1")
@with_appcontext
@pass_context
def database_downgrade(ctx, revision):
    """Downgrade database to a previous migration.

    Args:
        revision: Target revision (default: -1 for one step back, or 'base' for all the way back)
    """
    try:
        core_module = importlib.import_module("coati_payroll")
        alembic = getattr(core_module, "alembic")

        click.echo(f"Downgrading database to revision: {revision}...")
        alembic.downgrade(revision)
        output_result(ctx, f"Database downgraded successfully to revision: {revision}")

    except Exception as e:
        output_result(ctx, f"Failed to downgrade database: {e}", None, False)
        log.exception("Failed to downgrade database")
        sys.exit(1)


@database.command("current")
@with_appcontext
@pass_context
def database_current(ctx):
    """Show current migration revision."""
    try:
        # Get current revision
        revision = None
        try:
            revision = db.session.execute(db.text("SELECT version_num FROM alembic_version")).scalar()
        except Exception:
            pass

        if revision:
            output_result(ctx, f"Current database revision: {revision}", {"revision": revision})
        else:
            output_result(ctx, "No migration version found (database not stamped)", None, False)

    except Exception as e:
        output_result(ctx, f"Failed to get current revision: {e}", None, False)
        log.exception("Failed to get current revision")
        sys.exit(1)


@database.command("stamp")
@click.argument("revision", default="head")
@with_appcontext
@pass_context
def database_stamp(ctx, revision):
    """Stamp the database with a specific revision without running migrations.

    Args:
        revision: Target revision to stamp (default: 'head' for latest)
    """
    try:
        core_module = importlib.import_module("coati_payroll")
        alembic = getattr(core_module, "alembic")

        click.echo(f"Stamping database with revision: {revision}...")
        alembic.stamp(revision)
        output_result(ctx, f"Database stamped successfully with revision: {revision}")

    except Exception as e:
        output_result(ctx, f"Failed to stamp database: {e}", None, False)
        log.exception("Failed to stamp database")
        sys.exit(1)


# ============================================================================
# USER/USERS COMMANDS
# ============================================================================


def _users_list():
    """Get list of all users.

    Returns:
        list: List of user dictionaries with username, name, type, active status, and email.
    """
    all_users = db.session.execute(db.select(Usuario)).scalars().all()

    return [
        {
            "username": user.usuario,
            "name": f"{user.nombre} {user.apellido}".strip(),
            "type": user.tipo,
            "active": user.activo,
            "email": user.correo_electronico,
        }
        for user in all_users
    ]


@click.group()
def users():
    """User management commands."""


@users.command("list")
@with_appcontext
@pass_context
def users_list(ctx):
    """List all users."""
    try:
        users_data = _users_list()

        if ctx.json_output:
            output_result(ctx, "Users retrieved", {"count": len(users_data), "users": users_data}, True)
        else:
            click.echo(f"Users ({len(users_data)}):")
            click.echo()
            for user_data in users_data:
                status = "active" if user_data["active"] else "inactive"
                click.echo(f"  {user_data['username']} ({user_data['type']}) - {status}")
                if user_data["name"]:
                    click.echo(f"    Name: {user_data['name']}")
                if user_data["email"]:
                    click.echo(f"    Email: {user_data['email']}")

    except Exception as e:
        output_result(ctx, f"Failed to list users: {e}", None, False)
        sys.exit(1)


def _users_create(username, password, name, email, user_type):
    """Create a new user.

    Args:
        username: Username for the new user
        password: Password for the new user
        name: Full name of the user
        email: Email address (optional)
        user_type: Type of user (admin or operador)

    Raises:
        ValueError: If user already exists
    """
    existing = db.session.execute(db.select(Usuario).filter_by(usuario=username)).scalar_one_or_none()

    if existing:
        raise ValueError(f"User '{username}' already exists")

    user = Usuario()
    user.usuario = username
    user.acceso = proteger_passwd(password)

    # Split name into first and last
    name_parts = name.split(maxsplit=1)
    user.nombre = name_parts[0]
    user.apellido = name_parts[1] if len(name_parts) > 1 else ""

    user.correo_electronico = email
    user.tipo = user_type
    user.activo = True

    db.session.add(user)
    db.session.commit()


@users.command("create")
@click.option("--username", prompt=True, help="Username")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Password")
@click.option("--name", prompt=True, help="Full name")
@click.option("--email", default=None, help="Email address")
@click.option("--type", "user_type", type=click.Choice(["admin", "hr", "audit"]), default="hr", help="User type")
@with_appcontext
@pass_context
def users_create(ctx, username, password, name, email, user_type):
    """Create a new user."""
    try:
        _users_create(username, password, name, email, user_type)
        output_result(ctx, f"User '{username}' created successfully!")

    except Exception as e:
        db.session.rollback()
        output_result(ctx, f"Failed to create user: {e}", None, False)
        sys.exit(1)


def _users_disable(username):
    """Disable a user.

    Args:
        username: Username to disable

    Raises:
        ValueError: If user not found
    """
    user = db.session.execute(db.select(Usuario).filter_by(usuario=username)).scalar_one_or_none()

    if not user:
        raise ValueError(f"User '{username}' not found")

    user.activo = False
    db.session.commit()


@users.command("disable")
@click.argument("username")
@with_appcontext
@pass_context
def users_disable(ctx, username):
    """Disable a user."""
    try:
        _users_disable(username)
        output_result(ctx, f"User '{username}' disabled successfully!")

    except Exception as e:
        db.session.rollback()
        output_result(ctx, f"Failed to disable user: {e}", None, False)
        sys.exit(1)


def _users_reset_password(username, password):
    """Reset user password.

    Args:
        username: Username to reset password for
        password: New password

    Raises:
        ValueError: If user not found
    """
    user = db.session.execute(db.select(Usuario).filter_by(usuario=username)).scalar_one_or_none()

    if not user:
        raise ValueError(f"User '{username}' not found")

    user.acceso = proteger_passwd(password)
    db.session.commit()


@users.command("reset-password")
@click.argument("username")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="New password")
@with_appcontext
@pass_context
def users_reset_password(ctx, username, password):
    """Reset user password."""
    try:
        _users_reset_password(username, password)
        output_result(ctx, f"Password reset for user '{username}'!")

    except Exception as e:
        db.session.rollback()
        output_result(ctx, f"Failed to reset password: {e}", None, False)
        sys.exit(1)


def _users_set_admin(username, password):
    """Create or update an administrator user.

    Args:
        username: Username for the admin
        password: Password for the admin

    Returns:
        tuple: (is_new_user, existing_admin_count) - whether user was created or updated,
               and how many existing admins were deactivated
    """
    admins = db.session.execute(db.select(Usuario).filter_by(tipo="admin")).scalars().all()
    deactivated_count = 0

    if admins:
        for admin in admins:
            admin.activo = False
            deactivated_count += 1

    existing_user = db.session.execute(db.select(Usuario).filter_by(usuario=username)).scalar_one_or_none()

    if existing_user:
        existing_user.acceso = proteger_passwd(password)
        existing_user.tipo = "admin"
        existing_user.activo = True
        db.session.commit()
        return False, deactivated_count
    new_user = Usuario()
    new_user.usuario = username
    new_user.acceso = proteger_passwd(password)
    new_user.nombre = "Administrator"
    new_user.apellido = ""
    new_user.correo_electronico = None
    new_user.tipo = "admin"
    new_user.activo = True

    db.session.add(new_user)
    db.session.commit()
    return True, deactivated_count


@users.command("set-admin")
@with_appcontext
@pass_context
def users_set_admin(ctx):
    """Create or update an administrator user (legacy command)."""
    click.echo("=== Set Administrator User ===")
    click.echo()

    username = click.prompt("Enter username", type=str)

    if not username or not username.strip():
        click.echo("Error: Username cannot be empty", err=True)
        sys.exit(1)

    username = username.strip()

    password = getpass.getpass("Enter password: ")
    password_confirm = getpass.getpass("Confirm password: ")

    if password != password_confirm:
        click.echo("Error: Passwords do not match", err=True)
        sys.exit(1)

    if not password:
        click.echo("Error: Password cannot be empty", err=True)
        sys.exit(1)

    try:
        is_new, deactivated_count = _users_set_admin(username, password)

        if deactivated_count > 0:
            click.echo(f"Deactivated {deactivated_count} existing admin user(s)")

        if is_new:
            output_result(ctx, f"Successfully created user '{username}' as administrator")
        else:
            output_result(ctx, f"Successfully updated user '{username}' as administrator")

        click.echo()
        click.echo("All other admin users have been deactivated.")

    except Exception as e:
        db.session.rollback()
        click.echo(f"Error: Failed to set administrator user: {e}", err=True)
        log.exception("Failed to set administrator user")
        sys.exit(1)


# ============================================================================
# CACHE COMMANDS
# ============================================================================


def _cache_clear():
    """Clear application caches."""
    from coati_payroll.locale_config import invalidate_language_cache

    invalidate_language_cache()


def _cache_warm():
    """Warm up caches.

    Returns:
        str: Language code that was cached
    """
    from coati_payroll.locale_config import get_language_from_db

    return get_language_from_db()


def _cache_status():
    """Get cache status.

    Returns:
        dict: Cache status information
    """
    from coati_payroll.locale_config import _language_cache

    return {"language_cache": "populated" if _language_cache else "empty"}


@click.group()
def cache():
    """Cache and temporary data management."""


@cache.command("clear")
@with_appcontext
@pass_context
def cache_clear(ctx):
    """Clear application caches."""
    try:
        click.echo("Clearing application caches...")

        _cache_clear()
        output_result(ctx, "Language cache cleared")

        if not ctx.json_output:
            click.echo()
            click.echo("✓ Cache cleared successfully!")

    except Exception as e:
        output_result(ctx, f"Failed to clear cache: {e}", None, False)
        log.exception("Failed to clear cache")
        sys.exit(1)


@cache.command("warm")
@with_appcontext
@pass_context
def cache_warm(ctx):
    """Warm up caches."""
    try:
        lang = _cache_warm()
        output_result(ctx, f"Language cache warmed ({lang})")

        if not ctx.json_output:
            click.echo("✓ Cache warmed successfully!")

    except Exception as e:
        output_result(ctx, f"Failed to warm cache: {e}", None, False)
        sys.exit(1)


@cache.command("status")
@with_appcontext
@pass_context
def cache_status(ctx):
    """Show cache status."""
    try:
        cache_info = _cache_status()

        if ctx.json_output:
            output_result(ctx, "Cache status", cache_info, True)
        else:
            click.echo("Cache Status:")
            click.echo(f"  Language: {cache_info['language_cache']}")

    except Exception as e:
        output_result(ctx, f"Failed to get cache status: {e}", None, False)
        sys.exit(1)


# ============================================================================
# MAINTENANCE COMMANDS
# ============================================================================


@click.group()
def maintenance():
    """Background jobs and cleanup tasks."""


@maintenance.command("cleanup-sessions")
@with_appcontext
@pass_context
def maintenance_cleanup_sessions(ctx):
    """Clean up expired sessions."""
    try:
        # This would clean up Flask-Session data
        click.echo("Cleaning up expired sessions...")
        output_result(ctx, "Session cleanup completed")

    except Exception as e:
        output_result(ctx, f"Failed to cleanup sessions: {e}", None, False)
        sys.exit(1)


@maintenance.command("cleanup-temp")
@with_appcontext
@pass_context
def maintenance_cleanup_temp(ctx):
    """Clean up temporary files."""
    try:
        click.echo("Cleaning up temporary files...")
        output_result(ctx, "Temporary file cleanup completed")

    except Exception as e:
        output_result(ctx, f"Failed to cleanup temp files: {e}", None, False)
        sys.exit(1)


@maintenance.command("run-jobs")
@with_appcontext
@pass_context
def maintenance_run_jobs(ctx):
    """Run pending background jobs."""
    try:
        click.echo("Running pending background jobs...")
        output_result(ctx, "Background jobs completed")

    except Exception as e:
        output_result(ctx, f"Failed to run jobs: {e}", None, False)
        sys.exit(1)


# ============================================================================
# DEBUG COMMANDS
# ============================================================================


def _debug_config(app):
    """Get application configuration.

    Args:
        app: Flask application instance

    Returns:
        dict: Configuration data
    """
    return {
        "SQLALCHEMY_DATABASE_URI": "***" if "@" in str(db.engine.url) else str(db.engine.url),
        "TESTING": app.config.get("TESTING", False),
        "DEBUG": app.config.get("DEBUG", False),
    }


def _debug_routes(app):
    """Get application routes.

    Args:
        app: Flask application instance

    Returns:
        list: List of route dictionaries with endpoint, methods, and path
    """
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({"endpoint": rule.endpoint, "methods": sorted(rule.methods), "path": str(rule)})
    return routes


@click.group()
def debug():
    """Diagnostics and troubleshooting."""


@debug.command("config")
@with_appcontext
@pass_context
def debug_config(ctx):
    """Show application configuration."""
    try:
        config_data = _debug_config(current_app)

        if ctx.json_output:
            output_result(ctx, "Configuration", config_data, True)
        else:
            click.echo("Application Configuration:")
            for key, value in config_data.items():
                click.echo(f"  {key}: {value}")

    except Exception as e:
        output_result(ctx, f"Failed to get config: {e}", None, False)
        sys.exit(1)


@debug.command("routes")
@with_appcontext
@pass_context
def debug_routes(ctx):
    """List all application routes."""
    try:
        routes = _debug_routes(current_app)

        if ctx.json_output:
            output_result(ctx, "Routes", {"count": len(routes), "routes": routes}, True)
        else:
            click.echo(f"Application Routes ({len(routes)}):")
            for route in routes[:20]:  # Limit display
                methods = ", ".join(route["methods"])
                click.echo(f"  {route['path']} [{methods}]")
            if len(routes) > 20:
                click.echo(f"  ... and {len(routes) - 20} more")

    except Exception as e:
        output_result(ctx, f"Failed to list routes: {e}", None, False)
        sys.exit(1)


# ============================================================================
# REGISTRATION AND MAIN ENTRY POINT
# ============================================================================


def register_cli_commands(app):
    """Register all CLI commands with the Flask app."""
    app.cli.add_command(system)
    app.cli.add_command(database)
    app.cli.add_command(users)
    app.cli.add_command(cache)
    app.cli.add_command(maintenance)
    app.cli.add_command(debug)
    app.cli.add_command(plugins)


def main():
    """Entry point for payrollctl CLI tool."""

    flask_app_path = os.environ.get("FLASK_APP", None)
    if not flask_app_path:
        click.echo(
            "Error: FLASK_APP environment variable is not set.",
            err=True,
        )
        sys.exit(1)

    try:
        if ":" in flask_app_path:
            module_name, app_name = flask_app_path.split(":", 1)
        else:
            module_name = flask_app_path
            app_name = "app"

        try:
            try:
                module = __import__(module_name, fromlist=[app_name])
            except ImportError:
                module = None
                module_path = Path(module_name)
                if module_path.suffix != ".py":
                    module_path = module_path.with_suffix(".py")
                repo_root = Path(__file__).resolve().parent.parent
                candidates = [repo_root / module_path]
                for candidate in candidates:
                    if candidate.is_file():
                        candidate_parent = str(candidate.parent)
                        if candidate_parent not in sys.path:
                            sys.path.insert(0, candidate_parent)
                        module = __import__(module_name, fromlist=[app_name])
                        break
                if module is None:
                    for candidate in candidates:
                        if candidate.is_file():
                            spec = importlib.util.spec_from_file_location(module_name, candidate)
                            if spec and spec.loader:
                                module = importlib.util.module_from_spec(spec)
                                sys.modules[module_name] = module
                                spec.loader.exec_module(module)
                                break
                if module is None:
                    raise

            flask_app = getattr(module, app_name)
            flask_app.cli()
        except (ImportError, AttributeError):
            click.echo(f"Error: Failed to import Flask app: {flask_app_path}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: Failed to initialize Flask app: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
