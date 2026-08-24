# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.
"""Tests for PWA functionality (Manifest, Service Worker, Offline page)."""

import json


def test_manifest_endpoint_returns_json_and_200(client):
    """Test that /manifest.json returns status code 200, application/manifest+json, and valid PWA properties."""
    response = client.get("/manifest.json")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/manifest+json")

    data = json.loads(response.data)
    assert data["id"] == "/"
    assert data["name"] == "Coati Payroll"
    assert data["short_name"] == "Coati"
    assert data["start_url"] == "/"
    assert data["scope"] == "/"
    assert data["display"] == "standalone"
    assert data["orientation"] == "any"
    assert data["theme_color"] == "#5D4037"
    assert data["background_color"] == "#FAF8F6"
    assert isinstance(data["icons"], list)
    assert len(data["icons"]) >= 2

    sizes = [icon["sizes"] for icon in data["icons"]]
    assert "192x192" in sizes
    assert "512x512" in sizes


def test_service_worker_and_offline_page_accessible(client):
    """Test that sw.js and offline.html are accessible."""
    sw_response = client.get("/static/sw.js")
    assert sw_response.status_code == 200
    assert "CACHE_NAME" in sw_response.text

    offline_response = client.get("/static/offline.html")
    assert offline_response.status_code == 200
    assert "Sin conexión" in offline_response.text
