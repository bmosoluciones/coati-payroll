# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Add database-backed email recovery and trusted-browser security."""

from alembic import op
import sqlalchemy as sa


revision = "20260902_auth_email_security"
down_revision = "20260902_tenant_isolation"
branch_labels = None
depends_on = None


def _has_column(table_name, column_name):
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def _has_table(table_name):
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade():
    if not _has_column("usuario", "intentos_login_fallidos"):
        op.add_column(
            "usuario",
            sa.Column("intentos_login_fallidos", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column("usuario", "intentos_login_fallidos", server_default=None)
    if not _has_column("usuario", "bloqueado_hasta"):
        op.add_column("usuario", sa.Column("bloqueado_hasta", sa.DateTime(), nullable=True))

    if not _has_table("configuracion_correo"):
        op.create_table(
            "configuracion_correo",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("creado", sa.Date(), nullable=False),
            sa.Column("creado_por", sa.String(length=150), nullable=True),
            sa.Column("modificado", sa.DateTime(), nullable=True),
            sa.Column("modificado_por", sa.String(length=150), nullable=True),
            sa.Column("smtp_host", sa.String(length=255), nullable=True),
            sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
            sa.Column("smtp_username", sa.String(length=255), nullable=True),
            sa.Column("smtp_password_encrypted", sa.LargeBinary(), nullable=True),
            sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("smtp_use_ssl", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sender_email", sa.String(length=255), nullable=True),
            sa.Column("sender_name", sa.String(length=150), nullable=False, server_default="Coati Payroll"),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "proteger_inicio_sesion_origen_desconocido",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("codigo_login_expira_minutos", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("navegador_confiable_dias", sa.Integer(), nullable=False, server_default="30"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("token_correo"):
        op.create_table(
            "token_correo",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("creado", sa.Date(), nullable=False),
            sa.Column("creado_por", sa.String(length=150), nullable=True),
            sa.Column("modificado", sa.DateTime(), nullable=True),
            sa.Column("modificado_por", sa.String(length=150), nullable=True),
            sa.Column("usuario_id", sa.String(length=26), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("proposito", sa.String(length=40), nullable=False),
            sa.Column("expira_en", sa.DateTime(), nullable=False),
            sa.Column("usado_en", sa.DateTime(), nullable=True),
            sa.Column("intentos_fallidos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ip_solicitud", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_token_correo_hash"),
        )
        op.create_index("ix_token_correo_id", "token_correo", ["id"], unique=False)
        op.create_index("ix_token_correo_usuario_id", "token_correo", ["usuario_id"], unique=False)
        op.create_index("ix_token_correo_token_hash", "token_correo", ["token_hash"], unique=False)
        op.create_index("ix_token_correo_proposito", "token_correo", ["proposito"], unique=False)
        op.create_index("ix_token_correo_expira_en", "token_correo", ["expira_en"], unique=False)
        op.create_index("ix_token_correo_usuario_proposito", "token_correo", ["usuario_id", "proposito"], unique=False)

    if not _has_table("navegador_confiable"):
        op.create_table(
            "navegador_confiable",
            sa.Column("id", sa.String(length=26), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("creado", sa.Date(), nullable=False),
            sa.Column("creado_por", sa.String(length=150), nullable=True),
            sa.Column("modificado", sa.DateTime(), nullable=True),
            sa.Column("modificado_por", sa.String(length=150), nullable=True),
            sa.Column("usuario_id", sa.String(length=26), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("expira_en", sa.DateTime(), nullable=False),
            sa.Column("ultimo_uso_en", sa.DateTime(), nullable=True),
            sa.Column("revocado_en", sa.DateTime(), nullable=True),
            sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_navegador_confiable_hash"),
        )
        op.create_index("ix_navegador_confiable_id", "navegador_confiable", ["id"], unique=False)
        op.create_index("ix_navegador_confiable_usuario_id", "navegador_confiable", ["usuario_id"], unique=False)
        op.create_index("ix_navegador_confiable_token_hash", "navegador_confiable", ["token_hash"], unique=False)
        op.create_index("ix_navegador_confiable_expira_en", "navegador_confiable", ["expira_en"], unique=False)


def downgrade():
    bind = op.get_bind()
    for table_name in ("navegador_confiable", "token_correo", "configuracion_correo"):
        if sa.inspect(bind).has_table(table_name):
            op.drop_table(table_name)
    if _has_column("usuario", "bloqueado_hasta"):
        op.drop_column("usuario", "bloqueado_hasta")
    if _has_column("usuario", "intentos_login_fallidos"):
        op.drop_column("usuario", "intentos_login_fallidos")
