"""
Settings controller tests for user-owned API key behavior.
"""

from config import Config
from conftest import assert_success_response
from models import UserSettings

HIDDEN_USER_SETTING_KEYS = {
    "ai_provider_format",
    "api_base_url",
    "text_model",
    "image_model",
    "image_caption_model",
    "text_model_source",
    "image_model_source",
    "image_caption_model_source",
    "text_api_base_url",
    "image_api_base_url",
    "image_caption_api_base_url",
}


def test_default_openai_proxy_and_gpt_image_model_config():
    assert Config.AI_PROVIDER_FORMAT == "openai"
    assert Config.OPENAI_API_BASE == "https://ai.zh-zh.top/v1"
    assert Config.TEXT_MODEL == "gpt-5.5"
    assert Config.IMAGE_MODEL == "gpt-image-2"
    assert Config.IMAGE_CAPTION_MODEL == "gpt-5.5"


def test_settings_response_does_not_expose_hidden_proxy_or_model_config(client):
    response = client.get("/api/settings")
    data = assert_success_response(response)
    assert HIDDEN_USER_SETTING_KEYS.isdisjoint(data["data"].keys())

    active_config_response = client.get("/api/settings/active-config")
    assert active_config_response.status_code == 404


def test_update_settings_saves_only_user_api_key(client):
    response = client.put(
        "/api/settings",
        json={
            "api_key": " user-secret-key ",
            "ai_provider_format": "gemini",
            "api_base_url": "https://evil.example/v1",
            "text_model": "evil-text-model",
            "image_model": "evil-image-model",
            "image_caption_model": "evil-caption-model",
        },
    )
    data = assert_success_response(response)
    assert data["data"]["api_key_length"] == len("user-secret-key")
    assert HIDDEN_USER_SETTING_KEYS.isdisjoint(data["data"].keys())

    with client.application.app_context():
        settings = UserSettings.query.one()
        assert settings.api_key == "user-secret-key"
        assert settings.ai_provider_format is None
        assert settings.api_base_url is None
        assert settings.text_model is None
        assert settings.image_model is None
        assert settings.image_caption_model is None


def test_reset_settings_clears_user_api_key(client):
    assert_success_response(client.put("/api/settings", json={"api_key": "user-secret-key"}))

    response = client.post("/api/settings/reset")
    data = assert_success_response(response)
    assert data["data"]["api_key_length"] == 0
    assert HIDDEN_USER_SETTING_KEYS.isdisjoint(data["data"].keys())

    with client.application.app_context():
        settings = UserSettings.query.one()
        assert settings.api_key is None


def test_platform_settings_tests_are_not_user_accessible(client):
    response = client.post("/api/settings/tests/mineru-pdf", json={"api_key": "user-secret-key"})
    assert response.status_code == 404
