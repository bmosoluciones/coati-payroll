# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Unit tests for CLI module functions."""

from __future__ import annotations

import types
import tempfile
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from coati_payroll.auth import proteger_passwd
from coati_payroll.model import Usuario, db

# ============================================================================
# SYSTEM COMMANDS TESTS
# ============================================================================


def test_system_status(app, db_session):
    """Test _system_status returns correct data."""
    from coati_payroll.cli import _system_status

    with app.app_context():
        # Delete all admin users that may have been created during setup
        db_session.query(Usuario).filter_by(tipo="admin").delete()
        db_session.commit()

        # Create a single admin user manually
        admin = Usuario()
        admin.usuario = "admin-for-status"
        admin.acceso = proteger_passwd("password")
        admin.nombre = "Admin"
        admin.apellido = "Test"
        admin.tipo = "admin"
        admin.activo = True
        db_session.add(admin)
        db_session.commit()

        result = _system_status()

        assert result["database"] == "connected"
        assert result["admin_user"] == "active"
        assert "mode" in result


def test_system_status_no_admin(app, db_session):
    """Test _system_status when no admin user exists."""
    from coati_payroll.cli import _system_status

    with app.app_context():
        result = _system_status()

        assert result["database"] == "connected"
        assert result["admin_user"] == "none"


def test_system_check(app, db_session, admin_user):
    """Test _system_check returns checks."""
    from coati_payroll.cli import _system_check

    with app.app_context():
        checks = _system_check()

        assert len(checks) == 3
        assert any(c["name"] == "Database connection" for c in checks)
        assert any(c["name"] == "Active admin user" for c in checks)
        assert any(c["name"] == "Required tables" for c in checks)


def test_system_info(app, db_session):
    """Test _system_info returns system information."""
    from coati_payroll.cli import _system_info

    with app.app_context():
        info = _system_info()

        assert "version" in info
        assert "python" in info
        assert "database_uri" in info


def test_system_env():
    """Test _system_env returns environment variables."""
    from coati_payroll.cli import _system_env

    env_vars = _system_env()

    assert "FLASK_APP" in env_vars
    assert "FLASK_ENV" in env_vars
    assert "DATABASE_URL" in env_vars
    assert "ADMIN_USER" in env_vars
    assert "COATI_LANG" in env_vars


# ============================================================================
# DATABASE COMMANDS TESTS
# ============================================================================


def test_database_status(app, db_session):
    """Test _database_status returns database info."""
    from coati_payroll.cli import _database_status

    with app.app_context():
        result = _database_status()

        assert "tables" in result
        assert "table_names" in result
        assert "record_counts" in result
        assert isinstance(result["tables"], int)


def test_database_init(app, db_session):
    """Test _database_init initializes database."""
    from coati_payroll.cli import _database_init

    with app.app_context():
        admin_user = _database_init(app)

        assert admin_user is not None
        assert isinstance(admin_user, str)


def test_database_init_creates_all_metadata_tables(tmp_path):
    """Test _database_init creates every table declared in SQLAlchemy metadata."""
    from sqlalchemy import inspect
    from sqlalchemy.orm import scoped_session, sessionmaker

    from coati_payroll import create_app
    from coati_payroll.cli import _database_init
    from coati_payroll.model import db as local_db

    db_file = tmp_path / "database_init_schema_check.db"
    config = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SECRET_KEY": "test-secret-key",
    }
    app = create_app(config)

    with app.app_context():
        # Isolate session state to avoid bleed-over from other tests that
        # monkeypatch the global Flask-SQLAlchemy scoped session.
        original_session = local_db.session
        connection = local_db.engine.connect()
        local_session = scoped_session(sessionmaker(bind=connection, expire_on_commit=False))
        local_db.session = local_session

        try:
            _database_init(app)

            inspector = inspect(local_db.engine)
            created_tables = set(inspector.get_table_names())
            expected_tables = set(local_db.metadata.tables.keys())
            missing_tables = expected_tables - created_tables

            assert not missing_tables, f"Missing tables after database init: {sorted(missing_tables)}"
        finally:
            local_session.close()
            connection.close()
            local_db.session = original_session


def test_database_seed(app, db_session):
    """Test _database_seed loads initial data."""
    from coati_payroll.cli import _database_seed

    with app.app_context():
        # Should not raise an exception
        _database_seed()


def test_database_drop(app, db_session):
    """Test _database_drop removes all tables."""
    from coati_payroll.cli import _database_drop

    with app.app_context():
        # Should not raise an exception
        _database_drop()


def test_backup_sqlite(app, db_session):
    """Test _backup_sqlite creates backup file for in-memory database."""
    from coati_payroll.cli import _backup_sqlite

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            output_file = tmp.name

        try:
            # Use the actual in-memory database URL
            db_url = str(db.engine.url)

            # The function should handle in-memory databases
            result = _backup_sqlite(db_url, output_file)

            assert result.exists()
            assert str(result) == output_file
            # Verify file has some content (not empty)
            assert result.stat().st_size > 0
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()


def test_database_restore_sqlite(app, db_session):
    """Test _database_restore_sqlite restores from backup."""
    from coati_payroll.cli import _database_restore_sqlite

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            backup_file = tmp.name
            tmp.write(b"test data")

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            target_db = tmp.name

        try:
            db_url = f"sqlite:///{target_db}"
            _database_restore_sqlite(backup_file, db_url)

            assert Path(target_db).exists()
        finally:
            if Path(backup_file).exists():
                Path(backup_file).unlink()
            if Path(target_db).exists():
                Path(target_db).unlink()


def test_database_restore_sqlite_file_not_found(app, db_session):
    """Test _database_restore_sqlite raises error for missing file."""
    from coati_payroll.cli import _database_restore_sqlite

    with app.app_context():
        with pytest.raises(FileNotFoundError):
            _database_restore_sqlite("nonexistent.db", "sqlite:///test.db")


def test_database_restore_sqlite_memory_db_error(app, db_session):
    """Test _database_restore_sqlite raises error for in-memory database."""
    from coati_payroll.cli import _database_restore_sqlite

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            backup_file = tmp.name

        try:
            with pytest.raises(ValueError, match="Cannot restore to in-memory database"):
                _database_restore_sqlite(backup_file, "sqlite:///:memory:")
        finally:
            if Path(backup_file).exists():
                Path(backup_file).unlink()


# ============================================================================
# USER COMMANDS TESTS
# ============================================================================


def test_users_list(app, db_session, admin_user):
    """Test _users_list returns all users."""
    from coati_payroll.cli import _users_list

    with app.app_context():
        users = _users_list()

        assert len(users) >= 1
        assert any(u["username"] == "admin-test" for u in users)


def test_users_create(app, db_session):
    """Test _users_create creates a new user."""
    from coati_payroll.cli import _users_create

    with app.app_context():
        _users_create("testuser", "password123", "Test User", "test@example.com", "hr")

        user = db.session.execute(db.select(Usuario).filter_by(usuario="testuser")).scalar_one_or_none()
        assert user is not None
        assert user.nombre == "Test"
        assert user.apellido == "User"
        assert user.correo_electronico == "test@example.com"
        assert user.tipo == "hr"
        assert user.activo is True


def test_users_create_existing_user(app, db_session, admin_user):
    """Test _users_create raises error for existing user."""
    from coati_payroll.cli import _users_create

    with app.app_context():
        with pytest.raises(ValueError, match="already exists"):
            _users_create("admin-test", "password", "Admin Test", None, "admin")


def test_users_disable(app, db_session, admin_user):
    """Test _users_disable disables a user."""
    from coati_payroll.cli import _users_disable

    with app.app_context():
        _users_disable("admin-test")

        user = db.session.execute(db.select(Usuario).filter_by(usuario="admin-test")).scalar_one_or_none()
        assert user is not None
        assert user.activo is False


def test_users_disable_nonexistent(app, db_session):
    """Test _users_disable raises error for nonexistent user."""
    from coati_payroll.cli import _users_disable

    with app.app_context():
        with pytest.raises(ValueError, match="not found"):
            _users_disable("nonexistent")


def test_users_reset_password(app, db_session, admin_user):
    """Test _users_reset_password resets password."""
    from coati_payroll.cli import _users_reset_password

    with app.app_context():
        old_password = admin_user.acceso
        _users_reset_password("admin-test", "newpassword123")

        user = db.session.execute(db.select(Usuario).filter_by(usuario="admin-test")).scalar_one_or_none()
        assert user is not None
        assert user.acceso != old_password


def test_users_reset_password_nonexistent(app, db_session):
    """Test _users_reset_password raises error for nonexistent user."""
    from coati_payroll.cli import _users_reset_password

    with app.app_context():
        with pytest.raises(ValueError, match="not found"):
            _users_reset_password("nonexistent", "newpassword")


def test_users_set_admin_new_user(app, db_session):
    """Test _users_set_admin creates new admin user."""
    from coati_payroll.cli import _users_set_admin

    with app.app_context():
        is_new, deactivated = _users_set_admin("newadmin", "adminpass")

        assert is_new is True
        assert deactivated == 0

        user = db.session.execute(db.select(Usuario).filter_by(usuario="newadmin")).scalar_one_or_none()
        assert user is not None
        assert user.tipo == "admin"
        assert user.activo is True


def test_users_set_admin_existing_user(app, db_session, admin_user):
    """Test _users_set_admin updates existing user to admin."""
    from coati_payroll.cli import _users_set_admin

    with app.app_context():
        # Create a non-admin user
        user = Usuario()
        user.usuario = "regularuser"
        user.acceso = proteger_passwd("password")
        user.nombre = "Regular"
        user.apellido = "User"
        user.tipo = "hr"
        user.activo = True
        db_session.add(user)
        db_session.commit()

        is_new, deactivated = _users_set_admin("regularuser", "newpass")

        assert is_new is False
        assert deactivated == 1  # admin-test was deactivated

        user = db.session.execute(db.select(Usuario).filter_by(usuario="regularuser")).scalar_one_or_none()
        assert user is not None
        assert user.tipo == "admin"
        assert user.activo is True


# ============================================================================
# CACHE COMMANDS TESTS
# ============================================================================


def test_cache_clear(app, db_session):
    """Test _cache_clear clears caches."""
    from coati_payroll.cli import _cache_clear

    with app.app_context():
        # Should not raise an exception
        _cache_clear()


def test_cache_warm(app, db_session):
    """Test _cache_warm warms up caches."""
    from coati_payroll.cli import _cache_warm

    with app.app_context():
        lang = _cache_warm()
        assert lang is not None
        assert isinstance(lang, str)


def test_cache_status(app, db_session):
    """Test _cache_status returns cache status."""
    from coati_payroll.cli import _cache_status

    with app.app_context():
        status = _cache_status()
        assert "language_cache" in status


# ============================================================================
# DEBUG COMMANDS TESTS
# ============================================================================


def test_debug_config(app, db_session):
    """Test _debug_config returns configuration."""
    from coati_payroll.cli import _debug_config

    with app.app_context():
        config = _debug_config(app)

        assert "SQLALCHEMY_DATABASE_URI" in config
        assert "TESTING" in config
        assert "DEBUG" in config


def test_debug_routes(app, db_session):
    """Test _debug_routes returns routes."""
    from coati_payroll.cli import _debug_routes

    with app.app_context():
        routes = _debug_routes(app)

        assert len(routes) > 0
        assert all("endpoint" in r for r in routes)
        assert all("methods" in r for r in routes)
        assert all("path" in r for r in routes)


# ============================================================================
# BACKUP POSTGRESQL AND MYSQL TESTS (mocked)
# ============================================================================


def test_backup_postgresql(app, db_session, monkeypatch):
    """Test _backup_postgresql creates backup."""
    from coati_payroll.cli import _backup_postgresql
    import subprocess

    # Mock subprocess.run to avoid actually running pg_dump
    def mock_run(*args, **kwargs):
        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            output_file = tmp.name

        try:
            db_url = "postgresql://user:pass@localhost/dbname"
            result = _backup_postgresql(db_url, output_file)

            assert result == Path(output_file)
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()


def test_backup_postgresql_failure(app, db_session, monkeypatch):
    """Test _backup_postgresql handles pg_dump failure."""
    from coati_payroll.cli import _backup_postgresql
    import subprocess

    # Mock subprocess.run to simulate failure
    def mock_run(*args, **kwargs):
        class Result:
            returncode = 1
            stderr = "pg_dump error"

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            output_file = tmp.name

        try:
            db_url = "postgresql://user:pass@localhost/dbname"
            with pytest.raises(RuntimeError, match="pg_dump failed"):
                _backup_postgresql(db_url, output_file)
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()


def test_backup_mysql(app, db_session, monkeypatch):
    """Test _backup_mysql creates backup."""
    from coati_payroll.cli import _backup_mysql
    import subprocess

    # Mock subprocess.run to avoid actually running mysqldump
    def mock_run(*args, **kwargs):
        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            output_file = tmp.name

        try:
            db_url = "mysql://user:pass@localhost/dbname"
            result = _backup_mysql(db_url, output_file)

            assert result == Path(output_file)
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()


def test_backup_mysql_failure(app, db_session, monkeypatch):
    """Test _backup_mysql handles mysqldump failure."""
    from coati_payroll.cli import _backup_mysql
    import subprocess

    # Mock subprocess.run to simulate failure
    def mock_run(*args, **kwargs):
        class Result:
            returncode = 1
            stderr = "mysqldump error"

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            output_file = tmp.name

        try:
            db_url = "mysql://user:pass@localhost/dbname"
            with pytest.raises(RuntimeError, match="mysqldump failed"):
                _backup_mysql(db_url, output_file)
        finally:
            if Path(output_file).exists():
                Path(output_file).unlink()


# ============================================================================
# OUTPUT RESULT AND CONTEXT TESTS
# ============================================================================


def test_output_result_text(capsys):
    """Test output_result in text mode."""
    from coati_payroll.cli import output_result, CLIContext

    ctx = CLIContext()
    ctx.json_output = False

    output_result(ctx, "Test message", None, True)
    captured = capsys.readouterr()
    assert "✓ Test message" in captured.out


def test_output_result_json(capsys):
    """Test output_result in JSON mode."""
    from coati_payroll.cli import output_result, CLIContext
    import json

    ctx = CLIContext()
    ctx.json_output = True

    output_result(ctx, "Test message", {"key": "value"}, True)
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["success"] is True
    assert result["message"] == "Test message"
    assert result["data"]["key"] == "value"


def test_output_result_failure(capsys):
    """Test output_result with failure."""
    from coati_payroll.cli import output_result, CLIContext

    ctx = CLIContext()
    ctx.json_output = False

    output_result(ctx, "Error occurred", None, False)
    captured = capsys.readouterr()
    assert "✗ Error occurred" in captured.out


def test_cli_context():
    """Test CLIContext initialization."""
    from coati_payroll.cli import CLIContext

    ctx = CLIContext()
    assert ctx.environment is None
    assert ctx.json_output is False
    assert ctx.auto_yes is False


# ============================================================================
# ADDITIONAL INTEGRATION TESTS
# ============================================================================


def test_system_check_db_connection_failure(app, db_session, monkeypatch):
    """Test _system_check handles database connection failure."""
    from coati_payroll.cli import _system_check

    def mock_execute(*args, **kwargs):
        raise Exception("Connection failed")

    with app.app_context():
        # Temporarily break the database connection
        original_execute = db.session.execute
        monkeypatch.setattr(db.session, "execute", mock_execute)

        checks = _system_check()

        # Should have a failed database connection check
        db_check = next((c for c in checks if c["name"] == "Database connection"), None)
        assert db_check is not None
        assert db_check["status"] == "FAILED"

        # Restore original execute
        monkeypatch.setattr(db.session, "execute", original_execute)


def test_users_create_single_name(app, db_session):
    """Test _users_create with single name (no last name)."""
    from coati_payroll.cli import _users_create

    with app.app_context():
        _users_create("singlename", "password123", "SingleName", None, "hr")

        user = db.session.execute(db.select(Usuario).filter_by(usuario="singlename")).scalar_one_or_none()
        assert user is not None
        assert user.nombre == "SingleName"
        assert user.apellido == ""


def test_backup_sqlite_with_auto_timestamp(app, db_session):
    """Test _backup_sqlite generates timestamp in filename."""
    from coati_payroll.cli import _backup_sqlite

    with app.app_context():
        db_url = str(db.engine.url)

        # Call without specifying output file
        result = _backup_sqlite(db_url)

        try:
            assert result.exists()
            assert "coati_backup_" in str(result)
            assert result.suffix == ".db"
        finally:
            if result.exists():
                result.unlink()


def test_backup_postgresql_with_auto_timestamp(app, db_session, monkeypatch):
    """Test _backup_postgresql generates timestamp in filename."""
    from coati_payroll.cli import _backup_postgresql
    import subprocess

    def mock_run(*args, **kwargs):
        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        db_url = "postgresql://user:pass@localhost/dbname"

        # Call without specifying output file
        result = _backup_postgresql(db_url)

        try:
            # Check that a filename with timestamp was generated
            assert "coati_backup_" in str(result)
            assert result.suffix == ".sql"
        finally:
            if result.exists():
                result.unlink()


def test_backup_mysql_with_auto_timestamp(app, db_session, monkeypatch):
    """Test _backup_mysql generates timestamp in filename."""
    from coati_payroll.cli import _backup_mysql
    import subprocess

    def mock_run(*args, **kwargs):
        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        db_url = "mysql://user:pass@localhost/dbname"

        # Call without specifying output file
        result = _backup_mysql(db_url)

        try:
            # Check that a filename with timestamp was generated
            assert "coati_backup_" in str(result)
            assert result.suffix == ".sql"
        finally:
            if result.exists():
                result.unlink()


# ============================================================================
# CLI COMMAND TESTS (using CliRunner)
# ============================================================================


def test_system_env_command():
    """Test system env command."""
    from click.testing import CliRunner
    from coati_payroll.cli import system

    runner = CliRunner()
    result = runner.invoke(system, ["env"])
    assert result.exit_code == 0
    assert "FLASK_APP" in result.output


def test_register_cli_commands(app):
    """Test register_cli_commands adds commands to app."""
    from coati_payroll.cli import register_cli_commands

    # Count commands before
    initial_commands = len(app.cli.commands)

    register_cli_commands(app)

    # Check that commands were added
    assert len(app.cli.commands) >= initial_commands
    assert "system" in app.cli.commands
    assert "database" in app.cli.commands
    assert "users" in app.cli.commands
    assert "cache" in app.cli.commands
    assert "maintenance" in app.cli.commands
    assert "debug" in app.cli.commands
    assert "plugins" in app.cli.commands


def test_database_group_commands_success(app, monkeypatch):
    """Cover database command wrappers through Flask CLI runner."""
    import coati_payroll.cli as cli

    runner = app.test_cli_runner()

    monkeypatch.setattr(cli, "_database_status", lambda: {"tables": 1, "record_counts": {"usuario": 1}})
    monkeypatch.setattr(cli, "_database_init", lambda _app: "admin")
    monkeypatch.setattr(cli, "_database_seed", lambda: None)
    monkeypatch.setattr(cli, "_database_drop", lambda: None)
    monkeypatch.setattr(cli, "_database_restore_sqlite", lambda *_: None)
    monkeypatch.setattr(cli, "_database_migrate_upgrade", lambda: None)
    monkeypatch.setattr(cli.db.session, "execute", lambda *_: types.SimpleNamespace(scalar=lambda: "rev"))
    monkeypatch.setattr(
        cli,
        "importlib",
        types.SimpleNamespace(
            import_module=lambda *_: types.SimpleNamespace(
                alembic=types.SimpleNamespace(downgrade=lambda *_: None, stamp=lambda *_: None)
            )
        ),
    )

    for cmd in [
        ["database", "status"],
        ["database", "init"],
        ["database", "seed"],
        ["database", "drop", "--yes"],
        ["database", "restore", "tests/test_cli.py", "--yes"],
        ["database", "migrate"],
        ["database", "upgrade"],
        ["database", "downgrade", "base"],
        ["database", "current"],
        ["database", "stamp", "head"],
    ]:
        result = runner.invoke(args=cmd)
        assert result.exit_code == 0


def test_users_cache_maintenance_debug_and_serve_commands(app, monkeypatch):
    """Cover command wrappers for remaining groups with Flask CLI runner."""
    import coati_payroll.cli as cli

    runner = app.test_cli_runner()

    monkeypatch.setattr(
        cli, "_users_list", lambda: [{"username": "u", "type": "hr", "active": True, "name": "", "email": None}]
    )
    monkeypatch.setattr(cli, "_users_create", lambda *_: None)
    monkeypatch.setattr(cli, "_users_disable", lambda *_: None)
    monkeypatch.setattr(cli, "_users_reset_password", lambda *_: None)
    monkeypatch.setattr(cli, "_cache_clear", lambda: None)
    monkeypatch.setattr(cli, "_cache_warm", lambda: "es")
    monkeypatch.setattr(cli, "_cache_status", lambda: {"language_cache": "populated"})
    monkeypatch.setattr(cli, "_debug_config", lambda _app: {"DEBUG": False})
    monkeypatch.setattr(cli, "_debug_routes", lambda _app: [{"path": "/", "methods": ["GET"]}])

    command_inputs = {
        tuple(["users", "create", "--username", "u1", "--name", "User One", "--type", "hr"]): "abc123\nabc123\n",
        tuple(["users", "reset-password", "u1"]): "abc123\nabc123\n",
    }

    for cmd in [
        ["users", "list"],
        ["users", "create", "--username", "u1", "--name", "User One", "--type", "hr"],
        ["users", "disable", "u1"],
        ["users", "reset-password", "u1"],
        ["cache", "clear"],
        ["cache", "warm"],
        ["cache", "status"],
        ["maintenance", "cleanup-temp"],
        ["debug", "config"],
        ["debug", "routes"],
    ]:
        result = runner.invoke(args=cmd, input=command_inputs.get(tuple(cmd), None))
        assert result.exit_code == 0


def test_maintenance_commands_cleanup_real_resources_and_reject_stub(app, db_session, monkeypatch, tmp_path):
    """Maintenance commands delete their declared targets or fail explicitly."""
    import coati_payroll.cli as cli

    runner = app.test_cli_runner()
    with app.app_context():
        app.config["SESSION_TYPE"] = "sqlalchemy"
        app.config["SESSION_SQLALCHEMY_TABLE"] = "sessions"
        db_session.execute(
            db.text(
                "INSERT INTO sessions (session_id, data, expiry) "
                "VALUES ('expired', :data, :expiry), ('current', :data, :expiry_future)"
            ),
            {
                "data": b"test",
                "expiry": datetime.now(UTC) - timedelta(hours=1),
                "expiry_future": datetime.now(UTC) + timedelta(hours=1),
            },
        )
        db_session.commit()

        result = runner.invoke(args=["maintenance", "cleanup-sessions"])
        assert result.exit_code == 0
        assert db_session.execute(db.text("SELECT COUNT(*) FROM sessions")).scalar() == 1

        exports_dir = tmp_path / "exports" / "reports"
        exports_dir.mkdir(parents=True)
        expired_export = exports_dir / "expired.csv"
        expired_export.write_text("old", encoding="utf-8")
        recent_export = exports_dir / "recent.csv"
        recent_export.write_text("new", encoding="utf-8")
        old_timestamp = (datetime.now(UTC) - timedelta(days=8)).timestamp()
        os.utime(expired_export, (old_timestamp, old_timestamp))
        monkeypatch.setattr(cli, "DIRECTORIO_APP", tmp_path)

        result = runner.invoke(args=["maintenance", "cleanup-temp"])
        assert result.exit_code == 0
        assert not expired_export.exists()
        assert recent_export.exists()

        result = runner.invoke(args=["maintenance", "run-jobs"])
        assert result.exit_code != 0
        assert "not supported" in result.output


def test_maintenance_cleanup_audit_removes_expired_records(app, db_session, monkeypatch):
    """cleanup-audit deletes audit records older than the retention period."""
    import os

    from coati_payroll.model import SecurityAuditLog, db

    monkeypatch.setenv("COATI_AUDIT_RETENTION_DAYS", "2555")
    runner = app.test_cli_runner()
    with app.app_context():
        old = SecurityAuditLog(
            event="user_updated",
            actor="old-actor",
            target_username="old",
            success=True,
            details={},
        )
        recent = SecurityAuditLog(
            event="user_updated",
            actor="recent-actor",
            target_username="recent",
            success=True,
            details={},
        )
        db.session.add_all([old, recent])
        db.session.flush()
        old.timestamp = datetime.now(UTC) - timedelta(days=3000)
        recent.timestamp = datetime.now(UTC) - timedelta(days=1)
        db.session.commit()

        result = runner.invoke(args=["maintenance", "cleanup-audit"])

        assert result.exit_code == 0
        remaining = db.session.query(SecurityAuditLog).all()
        assert [entry.actor for entry in remaining] == ["recent-actor"]
        assert "Expired audit records removed" in result.output


def test_maintenance_cleanup_audit_rejects_non_positive_retention(app, db_session, monkeypatch):
    """cleanup-audit fails explicitly when retention is non-positive."""
    monkeypatch.setenv("COATI_AUDIT_RETENTION_DAYS", "0")
    runner = app.test_cli_runner()
    result = runner.invoke(args=["maintenance", "cleanup-audit"])
    assert result.exit_code != 0
    assert "must be greater than zero" in result.output


def test_plugins_group_and_main_paths(app, monkeypatch):
    """Cover dynamic plugins command and main() import paths."""
    import coati_payroll.cli as cli

    runner = app.test_cli_runner()

    class DummyPlugin:
        plugin_id = "demo"
        version = "1.0.0"

    record = types.SimpleNamespace(installed=True, active=False, distribution_name="dist-demo")

    class ScalarResult:
        def first(self):
            return record

    class ExecResult:
        def scalars(self):
            return ScalarResult()

    dummy_module = types.SimpleNamespace(
        __version__="1.2.3",
        __doc__="demo plugin",
        init=lambda: None,
        update=lambda: None,
        demo_data=lambda: None,
    )

    monkeypatch.setattr(cli, "discover_installed_plugins", lambda: [DummyPlugin()])
    monkeypatch.setattr(cli, "load_plugin_module", lambda *_: dummy_module)
    monkeypatch.setattr(cli, "sync_plugin_registry", lambda: None)
    monkeypatch.setattr(cli.db, "create_all", lambda: None)
    monkeypatch.setattr(cli.db.session, "execute", lambda *_: ExecResult())
    monkeypatch.setattr(cli.db.session, "commit", lambda: None)

    for cmd in [
        ["plugins", "demo", "init"],
        ["plugins", "demo", "update"],
        ["plugins", "demo", "demo_data"],
        ["plugins", "demo", "status"],
        ["plugins", "demo", "version"],
        ["plugins", "demo", "info"],
        ["plugins", "demo", "maintainer"],
        ["plugins", "demo", "mantainer"],
        ["plugins", "demo", "contact"],
        ["plugins", "demo", "enable"],
        ["plugins", "demo", "disable"],
    ]:
        result = runner.invoke(args=cmd)
        assert result.exit_code == 0

    monkeypatch.delenv("FLASK_APP", raising=False)
    with pytest.raises(SystemExit):
        cli.main()

    mini_app = Path("miniapp_for_test.py")
    mini_app.write_text("from flask import Flask\napp = Flask(__name__)\napp.cli = lambda: None\n", encoding="utf-8")
    try:
        monkeypatch.setenv("FLASK_APP", "miniapp_for_test")
        cli.main()
    finally:
        mini_app.unlink(missing_ok=True)


# ============================================================================
# EXTENDED SYSTEM/DATABASE/PLUGINS CLI COVERAGE TESTS
# ============================================================================


def test_system_status_json_and_error(app, db_session, monkeypatch):
    """Test system status JSON output and exception handling."""
    import coati_payroll.cli as cli

    with app.app_context():
        # Clean up existing admin users to prevent MultipleResultsFound
        db_session.query(Usuario).filter_by(tipo="admin").delete()
        db_session.commit()

        # Create one admin user
        admin = Usuario()
        admin.usuario = "admin-json-status"
        admin.acceso = proteger_passwd("password")
        admin.nombre = "Admin"
        admin.apellido = "Test"
        admin.tipo = "admin"
        admin.activo = True
        db_session.add(admin)
        db_session.commit()

    # Monkeypatch CLIContext to force JSON output
    original_init = cli.CLIContext.__init__

    def patched_init(self):
        original_init(self)
        self.json_output = True

    monkeypatch.setattr(cli.CLIContext, "__init__", patched_init)

    runner = app.test_cli_runner()

    # Test JSON output
    result = runner.invoke(args=["system", "status"])
    assert result.exit_code == 0, f"Command output: {result.output}"
    assert '"database":' in result.output

    # Test Exception handling in system status
    def mock_system_status():
        raise Exception("Status extraction failed")

    monkeypatch.setattr(cli, "_system_status", mock_system_status)
    result = runner.invoke(args=["system", "status"])
    assert result.exit_code == 1
    assert "Failed to get system status" in result.output


def test_system_check_json_and_error(app, monkeypatch):
    """Test system check JSON output and exception handling."""
    import coati_payroll.cli as cli

    # Monkeypatch CLIContext to force JSON output
    original_init = cli.CLIContext.__init__

    def patched_init(self):
        original_init(self)
        self.json_output = True

    monkeypatch.setattr(cli.CLIContext, "__init__", patched_init)

    runner = app.test_cli_runner()

    # Test JSON output
    result = runner.invoke(args=["system", "check"])
    assert result.exit_code == 0
    assert '"checks":' in result.output

    # Test Exception handling in system check
    def mock_system_check():
        raise Exception("Checking failed")

    monkeypatch.setattr(cli, "_system_check", mock_system_check)
    result = runner.invoke(args=["system", "check"])
    assert result.exit_code == 1
    assert "System check failed" in result.output


def test_system_info_json_and_error(app, monkeypatch):
    """Test system info JSON output and exception handling."""
    import coati_payroll.cli as cli

    # Monkeypatch CLIContext to force JSON output
    original_init = cli.CLIContext.__init__

    def patched_init(self):
        original_init(self)
        self.json_output = True

    monkeypatch.setattr(cli.CLIContext, "__init__", patched_init)

    runner = app.test_cli_runner()

    # Test JSON output
    result = runner.invoke(args=["system", "info"])
    assert result.exit_code == 0
    assert '"version":' in result.output

    # Test Exception handling in system info
    def mock_system_info():
        raise Exception("Info failed")

    monkeypatch.setattr(cli, "_system_info", mock_system_info)
    result = runner.invoke(args=["system", "info"])
    assert result.exit_code == 1
    assert "Failed to get system info" in result.output


def test_database_status_json_and_error(app, monkeypatch):
    """Test database status JSON output and exception handling."""
    import coati_payroll.cli as cli

    # Monkeypatch CLIContext to force JSON output
    original_init = cli.CLIContext.__init__

    def patched_init(self):
        original_init(self)
        self.json_output = True

    monkeypatch.setattr(cli.CLIContext, "__init__", patched_init)

    runner = app.test_cli_runner()

    # Test JSON output
    result = runner.invoke(args=["database", "status"])
    assert result.exit_code == 0
    assert '"tables":' in result.output

    # Test Exception handling in database status
    def mock_database_status():
        raise Exception("Database status extraction failed")

    monkeypatch.setattr(cli, "_database_status", mock_database_status)
    result = runner.invoke(args=["database", "status"])
    assert result.exit_code == 1
    assert "Failed to get database status" in result.output


def test_plugin_hooks_handling(app, monkeypatch):
    """Test _run_plugin_hook behaves properly under various conditions."""
    import coati_payroll.cli as cli
    import click
    import types

    ctx = cli.CLIContext()
    ctx.json_output = False

    # No callable hook or alias
    dummy_empty = types.SimpleNamespace()
    with pytest.raises(click.ClickException, match="Plugin does not provide callable"):
        cli._run_plugin_hook(ctx, dummy_empty, "non_existent_hook", "test_plugin")

    # Hook raises exception
    def bad_hook():
        raise ValueError("Bad hook error")

    dummy_bad = types.SimpleNamespace(error_hook=bad_hook)
    with pytest.raises(click.ClickException, match="Bad hook error"):
        cli._run_plugin_hook(ctx, dummy_bad, "error_hook", "test_plugin")


def test_toggle_plugin_error_handling(app, db_session, monkeypatch):
    """Test plugin toggle rollback and click exception generation."""
    import coati_payroll.cli as cli
    import click

    ctx = cli.CLIContext()
    monkeypatch.setattr(cli, "sync_plugin_registry", lambda: None)

    # Non-existent plugin active toggle should fail
    with pytest.raises(click.ClickException, match="Plugin no registrado"):
        cli._toggle_plugin_active("unknown_plugin", True, ctx)

    # Database commit exception triggering rollback
    from coati_payroll.model import PluginRegistry

    p = PluginRegistry(plugin_id="buggy_plugin", distribution_name="buggy_plugin", installed=True, active=False)
    db_session.add(p)
    db_session.commit()

    # Test disabled action branch
    cli._toggle_plugin_active("buggy_plugin", False, ctx)

    # Test not installed validation branch
    p2 = PluginRegistry(
        plugin_id="uninstalled_plugin", distribution_name="uninstalled_plugin", installed=False, active=False
    )
    db_session.add(p2)
    db_session.commit()
    with pytest.raises(click.ClickException, match="Plugin no está instalado"):
        cli._toggle_plugin_active("uninstalled_plugin", True, ctx)

    # Test commit error / rollback
    def mock_commit():
        raise Exception("Database integrity violation")

    monkeypatch.setattr(db_session, "commit", mock_commit)
    with pytest.raises(click.ClickException, match="Database integrity violation"):
        cli._toggle_plugin_active("buggy_plugin", True, ctx)


# ============================================================================
# DATABASE RESTORE - MYSQL AND POSTGRESQL TESTS
# ============================================================================


def test_database_restore_mysql_success(app, db_session, monkeypatch):
    """Test _database_restore_mysql successfully restores a MySQL database."""
    import subprocess
    from coati_payroll.cli import _database_restore_mysql

    # Mock subprocess.run to simulate successful restore
    def mock_run(*args, **kwargs):
        class Result:
            returncode = 0
            stderr = b""

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            backup_file = tmp.name
            tmp.write(b"SQL dump content")

        try:
            db_url = "mysql://user:pass@localhost:3306/dbname"
            # Should not raise
            _database_restore_mysql(backup_file, db_url)
        finally:
            if Path(backup_file).exists():
                Path(backup_file).unlink()


def test_database_restore_mysql_failure(app, db_session, monkeypatch):
    """Test _database_restore_mysql raises error on restore failure."""
    import subprocess
    from coati_payroll.cli import _database_restore_mysql

    # Mock subprocess.run to simulate failure
    def mock_run(*args, **kwargs):
        class Result:
            returncode = 1
            stderr = b"Access denied for user 'user'@'localhost'"

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            backup_file = tmp.name
            tmp.write(b"SQL dump content")

        try:
            db_url = "mysql://user:pass@localhost:3306/dbname"
            with pytest.raises(RuntimeError, match="MySQL restore failed"):
                _database_restore_mysql(backup_file, db_url)
        finally:
            if Path(backup_file).exists():
                Path(backup_file).unlink()


def test_database_restore_mysql_missing_file(app, db_session):
    """Test MySQL restore rejects a missing dump before invoking the client."""
    from coati_payroll.cli import _database_restore_mysql

    with app.app_context(), pytest.raises(FileNotFoundError, match="Backup file not found"):
        _database_restore_mysql("missing.sql", "mysql://user:pass@localhost/dbname")


def test_database_restore_postgresql_success(app, db_session, monkeypatch):
    """Test _database_restore_postgresql successfully restores a PostgreSQL database."""
    import subprocess
    from coati_payroll.cli import _database_restore_postgresql

    # Mock subprocess.run to simulate successful restore
    def mock_run(*args, **kwargs):
        class Result:
            returncode = 0
            stderr = b""

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            backup_file = tmp.name
            tmp.write(b"PostgreSQL dump content")

        try:
            db_url = "postgresql://user:pass@localhost:5432/dbname"
            # Should not raise
            _database_restore_postgresql(backup_file, db_url)
        finally:
            if Path(backup_file).exists():
                Path(backup_file).unlink()


def test_database_restore_postgresql_failure(app, db_session, monkeypatch):
    """Test _database_restore_postgresql raises error on restore failure."""
    import subprocess
    from coati_payroll.cli import _database_restore_postgresql

    # Mock subprocess.run to simulate failure
    def mock_run(*args, **kwargs):
        class Result:
            returncode = 1
            stderr = b"FATAL: Ident authentication failed for user 'user'"

        return Result()

    monkeypatch.setattr(subprocess, "run", mock_run)

    with app.app_context():
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            backup_file = tmp.name
            tmp.write(b"PostgreSQL dump content")

        try:
            db_url = "postgresql://user:pass@localhost:5432/dbname"
            with pytest.raises(RuntimeError, match="PostgreSQL restore failed"):
                _database_restore_postgresql(backup_file, db_url)
        finally:
            if Path(backup_file).exists():
                Path(backup_file).unlink()


def test_database_restore_postgresql_missing_file(app, db_session):
    """Test PostgreSQL restore rejects a missing dump before invoking psql."""
    from coati_payroll.cli import _database_restore_postgresql

    with app.app_context(), pytest.raises(FileNotFoundError, match="Backup file not found"):
        _database_restore_postgresql("missing.sql", "postgresql://user:pass@localhost/dbname")
