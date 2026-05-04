"""
Authentication and user data isolation tests.
"""

import pytest

from models import Project, UserSettings, UserTemplate, db
from conftest import assert_success_response


PASSWORD = "Password123!"


class TestAuthSecurityConfig:
    def test_rejects_wildcard_cors_with_credentials(self, monkeypatch):
        from app import create_app

        monkeypatch.setenv("CORS_ORIGINS", "*")
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            create_app()

    def test_requires_strong_secret_key_in_production(self, monkeypatch):
        from app import create_app

        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
        monkeypatch.setenv("SECRET_KEY", "your-secret-key-change-this")
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            create_app()

    def test_allows_strong_secret_key_in_production(self, monkeypatch):
        from app import create_app

        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        app = create_app()
        assert app.config["SECRET_KEY"] == "x" * 32

    def test_redacts_database_uri_for_startup_logs(self):
        from app import _safe_database_label

        uri = "postgresql://dbuser:secret-password@example.com/app"
        assert _safe_database_label(uri) == "postgresql://[redacted]"
        assert "secret-password" not in _safe_database_label(uri)


def register(client, email: str, password: str = PASSWORD):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": email.split("@")[0]},
    )


def login(client, email: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def logout(client):
    return client.post("/api/auth/logout")


class TestAuth:
    def test_register_login_me_logout(self, unauthenticated_client):
        response = register(unauthenticated_client, "alice@example.com")
        data = assert_success_response(response, 201)
        assert data["data"]["user"]["email"] == "alice@example.com"

        me_response = unauthenticated_client.get("/api/auth/me")
        me_data = assert_success_response(me_response)
        assert me_data["data"]["authenticated"] is True
        assert me_data["data"]["user"]["email"] == "alice@example.com"

        logout_response = logout(unauthenticated_client)
        assert_success_response(logout_response)

        me_response = unauthenticated_client.get("/api/auth/me")
        me_data = assert_success_response(me_response)
        assert me_data["data"]["authenticated"] is False

    def test_reject_duplicate_email(self, unauthenticated_client):
        assert register(unauthenticated_client, "alice@example.com").status_code == 201
        response = register(unauthenticated_client, "alice@example.com")
        assert response.status_code == 409

    def test_protected_api_requires_login(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/projects")
        assert response.status_code == 401

    def test_reject_wrong_password(self, unauthenticated_client):
        assert register(unauthenticated_client, "alice@example.com").status_code == 201
        logout(unauthenticated_client)
        response = login(unauthenticated_client, "alice@example.com", "wrong-password")
        assert response.status_code == 401

    def test_rate_limits_login_attempts_by_client_ip(self, unauthenticated_client):
        unauthenticated_client.application.config["AUTH_RATE_LIMIT_ATTEMPTS"] = 2
        unauthenticated_client.application.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"] = 60

        first = login(unauthenticated_client, "missing@example.com")
        second = login(unauthenticated_client, "missing@example.com")
        limited = login(unauthenticated_client, "missing@example.com")

        assert first.status_code == 401
        assert second.status_code == 401
        assert limited.status_code == 429
        assert int(limited.headers["Retry-After"]) > 0

    def test_rate_limits_register_attempts_by_client_ip(self, unauthenticated_client):
        unauthenticated_client.application.config["AUTH_RATE_LIMIT_ATTEMPTS"] = 1
        unauthenticated_client.application.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"] = 60

        first = unauthenticated_client.post(
            "/api/auth/register",
            json={"email": "bad-email", "password": PASSWORD},
        )
        limited = unauthenticated_client.post(
            "/api/auth/register",
            json={"email": "bad-email", "password": PASSWORD},
        )

        assert first.status_code == 400
        assert limited.status_code == 429

    def test_ignores_forwarded_for_from_untrusted_peer(self, unauthenticated_client):
        unauthenticated_client.application.config["AUTH_RATE_LIMIT_ATTEMPTS"] = 1
        unauthenticated_client.application.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"] = 60
        unauthenticated_client.application.config["AUTH_TRUSTED_PROXIES"] = ["127.0.0.1"]

        first = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": PASSWORD},
            environ_base={"REMOTE_ADDR": "203.0.113.10"},
            headers={"X-Forwarded-For": "198.51.100.1"},
        )
        limited = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": PASSWORD},
            environ_base={"REMOTE_ADDR": "203.0.113.10"},
            headers={"X-Forwarded-For": "198.51.100.2"},
        )

        assert first.status_code == 401
        assert limited.status_code == 429

    def test_uses_forwarded_for_from_private_docker_proxy_by_default(self, unauthenticated_client):
        unauthenticated_client.application.config["AUTH_RATE_LIMIT_ATTEMPTS"] = 1
        unauthenticated_client.application.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"] = 60

        first = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": PASSWORD},
            environ_base={"REMOTE_ADDR": "172.18.0.3"},
            headers={"X-Forwarded-For": "198.51.100.1"},
        )
        second_client = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": PASSWORD},
            environ_base={"REMOTE_ADDR": "172.18.0.3"},
            headers={"X-Forwarded-For": "198.51.100.2"},
        )

        assert first.status_code == 401
        assert second_client.status_code == 401


class TestUserIsolation:
    def test_projects_are_scoped_to_current_user(self, unauthenticated_client):
        assert register(unauthenticated_client, "alice@example.com").status_code == 201
        alice_project = unauthenticated_client.post(
            "/api/projects",
            json={"creation_type": "idea", "idea_prompt": "Alice PPT"},
        )
        alice_data = assert_success_response(alice_project, 201)
        alice_project_id = alice_data["data"]["project_id"]
        logout(unauthenticated_client)

        assert register(unauthenticated_client, "bob@example.com").status_code == 201
        bob_project = unauthenticated_client.post(
            "/api/projects",
            json={"creation_type": "idea", "idea_prompt": "Bob PPT"},
        )
        bob_data = assert_success_response(bob_project, 201)
        bob_project_id = bob_data["data"]["project_id"]

        list_response = unauthenticated_client.get("/api/projects")
        list_data = assert_success_response(list_response)
        project_ids = {item["project_id"] for item in list_data["data"]["projects"]}
        assert project_ids == {bob_project_id}

        assert unauthenticated_client.get(f"/api/projects/{alice_project_id}").status_code == 404
        assert unauthenticated_client.get(f"/api/projects/{bob_project_id}").status_code == 200

    def test_ownerless_old_projects_are_hidden(self, client):
        with client.application.app_context():
            old_project = Project(creation_type="idea", idea_prompt="old data", status="DRAFT")
            db.session.add(old_project)
            db.session.commit()
            old_project_id = old_project.id

        list_response = client.get("/api/projects")
        list_data = assert_success_response(list_response)
        project_ids = {item["project_id"] for item in list_data["data"]["projects"]}
        assert old_project_id not in project_ids
        assert client.get(f"/api/projects/{old_project_id}").status_code == 404

    def test_user_templates_are_scoped_to_current_user(self, unauthenticated_client):
        assert register(unauthenticated_client, "alice@example.com").status_code == 201
        with unauthenticated_client.application.app_context():
            from models import User

            alice = User.query.filter_by(email="alice@example.com").first()
            alice_template = UserTemplate(
                user_id=alice.id,
                name="alice",
                file_path="user-templates/alice/a.png",
            )
            db.session.add(alice_template)
            db.session.commit()
            alice_template_id = alice_template.id
        logout(unauthenticated_client)

        assert register(unauthenticated_client, "bob@example.com").status_code == 201
        with unauthenticated_client.application.app_context():
            from models import User

            bob = User.query.filter_by(email="bob@example.com").first()
            bob_template = UserTemplate(
                user_id=bob.id,
                name="bob",
                file_path="user-templates/bob/b.png",
            )
            db.session.add(bob_template)
            db.session.commit()
            bob_template_id = bob_template.id

        response = unauthenticated_client.get("/api/user-templates")
        data = assert_success_response(response)
        template_ids = {item["template_id"] for item in data["data"]["templates"]}
        assert template_ids == {bob_template_id}
        assert alice_template_id not in template_ids


class TestUserSettingsIsolation:
    def test_user_settings_only_accept_api_key_and_ignore_base_model_overrides(self, client):
        response = client.put(
            "/api/settings",
            json={
                "api_key": " user-secret-key ",
                "api_base_url": "https://evil.example/v1",
                "ai_provider_format": "gemini",
                "text_model": "evil-text-model",
                "image_model": "evil-image-model",
            },
        )
        data = assert_success_response(response)
        assert data["data"]["api_key_length"] == len("user-secret-key")

        with client.application.app_context():
            settings = UserSettings.query.one()
            assert settings.api_key == "user-secret-key"
            assert settings.api_base_url is None
            assert settings.ai_provider_format is None
            assert settings.text_model is None
            assert settings.image_model is None

    def test_platform_settings_tests_are_not_available_to_users(self, client):
        response = client.post("/api/settings/tests/mineru-pdf", json={"api_key": "test-key"})
        assert response.status_code == 404
