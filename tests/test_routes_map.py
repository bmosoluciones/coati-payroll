"""Smoke test: recorre el mapa de URLs y valida que no hay rutas rotas."""

import pytest

REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}

# Matriz de roles que vamos a probar: anónimo y administrador
ROLE_MATRIX = [
    ("anon", None, True),
    ("admin", None, True),
]

# Rutas que legítimamente pueden redirigir para admin (p.ej., logout)
ADMIN_REDIRECT_ALLOWED_PATHS = {
    "/auth/logout",
}

# Rutas GET que no devuelven HTML (JSON/health) o que deben excluirse del barrido
EXCLUDED_PATHS = {
    "/health",
    "/ready",
}


def _collect_static_routes(app) -> list[str]:
    """Retorna rutas GET sin segmentos dinámicos."""
    rutas: list[str] = []
    for rule in app.url_map.iter_rules():
        # Excluir rutas con parámetros dinámicos
        if "<" in rule.rule:
            continue
        # Solo probar métodos GET
        if "GET" not in rule.methods:
            continue
        # Ignorar archivos estáticos
        if rule.endpoint.startswith("static"):
            continue
        # Excluir rutas conocidas que no devuelven HTML
        if rule.rule in EXCLUDED_PATHS:
            continue
        rutas.append(rule.rule)
    return sorted(set(rutas))


def _assert_response(route: str, role: str, allow_redirects: bool, response):
    # Versioned API routes intentionally require a bearer token, including
    # when the browser session belongs to an administrator.
    if route.startswith("/api/v1/") and response.status_code == 401:
        return

    # Para usuarios no admin, un 403 en rutas protegidas es aceptable
    if response.status_code == 403 and role != "admin":
        return

    # No se permiten errores 404/5xx
    if response.status_code in (404, 500) or response.status_code >= 500:
        pytest.fail(f"{route} para {role} devolvió un error {response.status_code}")

    # Manejo de redirecciones
    if response.status_code in REDIRECT_STATUS_CODES:
        if not allow_redirects:
            pytest.fail(f"{route} no debería redirigir para {role}")
        return

    # Para 200/201/204, no verificar Content-Type estrictamente: algunas rutas devuelven JSON
    if response.status_code >= 400:
        pytest.fail(f"{route} para {role} devolvió estado {response.status_code}")


@pytest.mark.parametrize("role, credentials, allow_redirects", ROLE_MATRIX)
def test_all_registered_routes_are_accessible(app, client, db_session, admin_user, role, credentials, allow_redirects):
    # Recolectar rutas
    routes = _collect_static_routes(app)

    # Preparar credenciales para admin usando el fixture
    if role == "admin":
        credentials = {"email": admin_user.usuario, "password": "admin-password"}

    # Autenticación si aplica
    if credentials:
        # Seguir redirecciones asegura que la sesión quede establecida en el cliente
        login_response = client.post("/auth/login", data=credentials, follow_redirects=True)
        assert login_response.status_code in {200, 201}

    # Probar todas las rutas recolectadas
    for route in routes:
        response = client.get(route, follow_redirects=False)
        _assert_response(route, role, allow_redirects, response)
