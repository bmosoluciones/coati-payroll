# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Repository for ConfiguracionCalculos operations."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from coati_payroll.model import ConfiguracionCalculos
from .base_repository import BaseRepository


class ConfigRepository(BaseRepository[ConfiguracionCalculos]):
    """Repository for ConfiguracionCalculos operations."""

    def get_by_id(self, config_id: str) -> Optional[ConfiguracionCalculos]:
        """Get configuration by ID."""
        return self.session.get(ConfiguracionCalculos, config_id)

    @staticmethod
    def _is_production() -> bool:
        """Detect whether the application is running in production mode."""
        from coati_payroll import config

        return not config.DESARROLLO and not config.TESTING

    def _fetch_unique(
        self, stmt, *, empresa_id: str | None, contexto: str
    ) -> Optional[ConfiguracionCalculos]:
        """Fetch at most one active config, warning on duplicate rows.

        Uses a deterministic ordering instead of ``scalar_one_or_none`` so a
        duplicate row can never make the payroll calculation explode.
        """
        from coati_payroll.log import log

        configs = (
            self.session.execute(
                stmt.order_by(ConfiguracionCalculos.creado.desc(), ConfiguracionCalculos.id)
            )
            .scalars()
            .all()
        )
        if not configs:
            return None
        if len(configs) > 1:
            log.warning(
                "ConfiguracionCalculos duplicada en contexto '%s' (empresa_id=%s); "
                "se usará la más reciente. Revise los registros para evitar ambigüedad.",
                contexto,
                empresa_id,
            )
        return configs[0]

    def get_for_empresa(self, empresa_id: Optional[str]) -> ConfiguracionCalculos:
        """Get configuration for empresa, or global default.

        Falls back to a global configuration and finally to hardcoded example
        defaults. Every fallback is logged (and rejected in production) so a
        payroll is never calculated silently with invented rules.
        """
        from sqlalchemy import select

        from coati_payroll.log import log

        # Try company-specific configuration
        if empresa_id:
            config = self._fetch_unique(
                select(ConfiguracionCalculos).filter(
                    ConfiguracionCalculos.empresa_id == empresa_id,
                    ConfiguracionCalculos.activo.is_(True),
                ),
                empresa_id=empresa_id,
                contexto="empresa",
            )
            if config:
                return config

        # Try global default
        config = self._fetch_unique(
            select(ConfiguracionCalculos).filter(
                ConfiguracionCalculos.empresa_id.is_(None),
                ConfiguracionCalculos.pais_id.is_(None),
                ConfiguracionCalculos.activo.is_(True),
            ),
            empresa_id=empresa_id,
            contexto="global",
        )

        if config:
            if empresa_id:
                log.warning(
                    "Empresa %s no tiene ConfiguracionCalculos propia; usando la configuración global. "
                    "Configure reglas de cálculo explícitas para la empresa antes de operar en producción.",
                    empresa_id,
                )
            return config

        if self._is_production():
            raise RuntimeError(
                "No existe ConfiguracionCalculos activa para la empresa "
                f"{empresa_id or 'N/A'} ni una configuración global. "
                "En producción se requiere configuración explícita; no se usarán valores de ejemplo."
            )

        # Return default instance (not saved to DB)
        # =====================================================================
        # DEFAULT VALUES DISCLAIMER (Per Social Contract)
        # =====================================================================
        # These default values are provided SOLELY to facilitate initial adoption.
        # They do NOT represent legal rules for any specific jurisdiction.
        # They are completely configurable by the implementer.
        # They should NOT be assumed as correct for any specific jurisdiction.
        #
        # Implementers MUST review and configure these values according to
        # their specific legal and business requirements before production use.
        # =====================================================================
        log.warning(
            "No existe ConfiguracionCalculos para empresa %s; usando valores de ejemplo por defecto. "
            "Estos valores NO representan reglas legales de ninguna jurisdicción y deben configurarse.",
            empresa_id or "N/A",
        )
        return ConfiguracionCalculos(
            empresa_id=None,
            pais_id=None,
            dias_mes_nomina=30,  # Example default - configure per jurisdiction
            dias_anio_nomina=365,  # Example default - configure per jurisdiction
            horas_jornada_diaria=Decimal("8.00"),  # Example default - configure per jurisdiction
            dias_mes_vacaciones=30,  # Example default - configure per jurisdiction
            dias_anio_vacaciones=365,  # Example default - configure per jurisdiction
            considerar_bisiesto_vacaciones=True,  # Example default - configure per jurisdiction
            dias_anio_financiero=365,  # Example default - configure per jurisdiction
            meses_anio_financiero=12,  # Example default - configure per jurisdiction
            dias_quincena=15,  # Example default - configure per jurisdiction
            liquidacion_modo_dias="calendario",
            liquidacion_factor_calendario=30,
            liquidacion_factor_laboral=28,
            dias_mes_antiguedad=30,  # Example default - configure per jurisdiction
            dias_anio_antiguedad=365,  # Example default - configure per jurisdiction
            activo=True,
        )

    def save(self, config: ConfiguracionCalculos) -> ConfiguracionCalculos:
        """Save configuration."""
        self.session.add(config)
        return config
