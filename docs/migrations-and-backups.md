# Migrations and backups

Fresh databases are created by the Alembic chain beginning at
`20260902_baseline`; subsequent releases add one revision and must be applied
with `payrollctl database migrate`.  Existing databases created with
`create_all` should be stamped once with `payrollctl database stamp head` after
an operator verifies their schema.

The backup unit in `ops/backup` runs a native dump, checks that the dump can be
listed or passes SQLite integrity checking, and removes files older than
`RETENTION_DAYS`.  Restore is available through
`payrollctl database restore`: SQLite copies a database file, PostgreSQL uses
`pg_restore` for custom dumps (or `psql` for plain SQL), and MySQL uses the
`mysql` client.
