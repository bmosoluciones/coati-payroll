# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Add explicit tenant memberships and concept company scopes.

The association tables are intentionally empty for concepts: an empty
association means that the concept remains global. Existing active users are
initially associated with every active company so the migration does not
silently remove access during rollout; administrators can narrow those
memberships afterwards.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260902_tenant_isolation"
down_revision = None
branch_labels = None
depends_on = None


def _create_if_missing(table_name, *columns):
    """Create a new association table on databases without the new schema."""
    bind = op.get_bind()
    if sa.inspect(bind).has_table(table_name):
        return False
    op.create_table(table_name, *columns)
    return True


def upgrade():
    usuario_empresa_created = _create_if_missing(
        "usuario_empresa",
        sa.Column("usuario_id", sa.String(length=26), nullable=False),
        sa.Column("empresa_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        sa.PrimaryKeyConstraint("usuario_id", "empresa_id"),
    )
    _create_if_missing(
        "empresa_percepcion",
        sa.Column("empresa_id", sa.String(length=26), nullable=False),
        sa.Column("concept_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        sa.ForeignKeyConstraint(["concept_id"], ["percepcion.id"]),
        sa.PrimaryKeyConstraint("empresa_id", "concept_id"),
    )
    _create_if_missing(
        "empresa_deduccion",
        sa.Column("empresa_id", sa.String(length=26), nullable=False),
        sa.Column("concept_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        sa.ForeignKeyConstraint(["concept_id"], ["deduccion.id"]),
        sa.PrimaryKeyConstraint("empresa_id", "concept_id"),
    )
    _create_if_missing(
        "empresa_prestacion",
        sa.Column("empresa_id", sa.String(length=26), nullable=False),
        sa.Column("concept_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        sa.ForeignKeyConstraint(["concept_id"], ["prestacion.id"]),
        sa.PrimaryKeyConstraint("empresa_id", "concept_id"),
    )

    if usuario_empresa_created:
        usuario = sa.table(
            "usuario",
            sa.column("id", sa.String(length=26)),
            sa.column("activo", sa.Boolean()),
        )
        empresa = sa.table(
            "empresa",
            sa.column("id", sa.String(length=26)),
            sa.column("activo", sa.Boolean()),
        )
        usuario_empresa = sa.table(
            "usuario_empresa",
            sa.column("usuario_id", sa.String(length=26)),
            sa.column("empresa_id", sa.String(length=26)),
        )
        op.get_bind().execute(
            sa.insert(usuario_empresa).from_select(
                [usuario_empresa.c.usuario_id, usuario_empresa.c.empresa_id],
                sa.select(usuario.c.id, empresa.c.id)
                .select_from(usuario.join(empresa, sa.true()))
                .where(
                    usuario.c.activo.is_(True),
                    empresa.c.activo.is_(True),
                ),
            )
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in (
        "empresa_prestacion",
        "empresa_deduccion",
        "empresa_percepcion",
        "usuario_empresa",
    ):
        if inspector.has_table(table_name):
            op.drop_table(table_name)
