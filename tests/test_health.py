"""The Phase 3 application responds before later features exist."""

import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_home_page_names_the_hub(client):
    response = client.get("/login")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "DNSC e-Clearance Hub" in page
    assert "css/app.css" in page
    assert 'for="email"' in page
    assert 'for="password"' in page


def test_dashboards_require_sign_in(client):
    assert client.get("/student", follow_redirects=False).status_code == 302
    assert client.get("/staff", follow_redirects=False).status_code == 302


def test_missing_secret_key_stops_startup(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()
