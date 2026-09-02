# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Create the initial Coati Payroll schema.

The project historically created tables with ``db.create_all`` and therefore
had no revision that represented a fresh installation.  Keeping the baseline
as the first revision lets existing installations be stamped at this point,
while fresh installations get the complete ORM schema before incremental
revisions run.
"""

from alembic import op


revision = "20260902_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create all tables that belong to the current ORM baseline."""
    from coati_payroll.model import db

    db.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    """Leave the baseline in place when rolling back incremental revisions.

    Dropping every application table is intentionally not part of an
    ordinary downgrade.  Database destruction remains an explicit
    ``payrollctl database drop`` operation.
    """


