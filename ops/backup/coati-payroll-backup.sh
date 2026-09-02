#!/usr/bin/env sh
# SPDX-License-Identifier: Apache-2.0
# Create and verify a native database backup.  Configure DATABASE_URL and
# BACKUP_DIR in the service environment rather than putting credentials here.
set -eu

BACKUP_DIR=${BACKUP_DIR:-/var/backups/coati-payroll}
RETENTION_DAYS=${RETENTION_DAYS:-14}
mkdir -p "$BACKUP_DIR"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

case "${DATABASE_URL:?DATABASE_URL is required}" in
  sqlite://*)
    source_path=${DATABASE_URL#sqlite:///}
    destination="$BACKUP_DIR/coati-$timestamp.sqlite"
    sqlite3 "$source_path" ".backup '$destination'"
    sqlite3 "$destination" "PRAGMA integrity_check" | grep -qx ok
    ;;
  postgresql://*|postgres://*)
    destination="$BACKUP_DIR/coati-$timestamp.dump"
    pg_dump --format=custom --no-owner "$DATABASE_URL" > "$destination"
    pg_restore --list "$destination" >/dev/null
    ;;
  mysql://*)
    destination="$BACKUP_DIR/coati-$timestamp.sql"
    mysqldump "$DATABASE_URL" > "$destination"
    test -s "$destination"
    ;;
  *) echo "Unsupported DATABASE_URL" >&2; exit 2 ;;
esac

find "$BACKUP_DIR" -type f -name 'coati-*' -mtime "+$RETENTION_DAYS" -delete
printf '%s\n' "$destination"
