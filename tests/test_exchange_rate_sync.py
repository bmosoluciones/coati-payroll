"""Tests for scheduled exchange-rate synchronization."""

import io
import json
from datetime import date

from coati_payroll.model import Moneda, TipoCambio, db
from coati_payroll.queue import tasks


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_sync_exchange_rates_upserts_configured_currencies(app, db_session, monkeypatch):
    with app.app_context():
        usd = Moneda(codigo="USD", nombre="US Dollar", activo=True)
        eur = Moneda(codigo="EUR", nombre="Euro", activo=True)
        db_session.add_all([usd, eur])
        db_session.flush()

        payload = {"base": "USD", "date": "2026-09-02", "rates": {"EUR": 0.91, "GBP": 0.84}}
        monkeypatch.setattr(tasks, "urlopen", lambda *args, **kwargs: _Response(json.dumps(payload).encode()))

        result = tasks.sync_exchange_rates(
            source_url="https://example.test/rates", base_currency="USD", primary_currencies={"EUR"}
        )

        assert result["synced"] == 1
        assert result["skipped"] == 1
        rate = db_session.execute(db.select(TipoCambio).filter_by(moneda_destino_id=eur.id)).scalar_one()
        assert rate.fecha == date(2026, 9, 2)
        assert str(rate.tasa) == "0.9100000000"


def test_sync_exchange_rates_rolls_back_when_a_primary_rate_is_invalid(app, db_session, monkeypatch):
    with app.app_context():
        usd = Moneda(codigo="USD", nombre="US Dollar", activo=True)
        eur = Moneda(codigo="EUR", nombre="Euro", activo=True)
        gbp = Moneda(codigo="GBP", nombre="Pound", activo=True)
        db_session.add_all([usd, eur, gbp])
        db_session.flush()
        payload = {"base": "USD", "date": "2026-09-02", "rates": {"EUR": 0.91, "GBP": "invalid"}}
        monkeypatch.setattr(tasks, "urlopen", lambda *args, **kwargs: _Response(json.dumps(payload).encode()))

        try:
            tasks.sync_exchange_rates(
                source_url="https://example.test/rates", base_currency="USD", primary_currencies={"EUR", "GBP"}
            )
        except ValueError as error:
            assert "Invalid exchange rate" in str(error)
        else:
            raise AssertionError("Invalid provider data should fail")

        assert db_session.execute(db.select(TipoCambio)).scalars().all() == []
