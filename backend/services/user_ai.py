"""User-scoped AI configuration helpers."""
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from flask import current_app

from config import Config
from models import UserSettings
from services.ai_providers import (
    LAZYLLM_VENDORS,
    AnthropicImageProvider,
    AnthropicTextProvider,
    GenAIImageProvider,
    GenAITextProvider,
    LazyLLMImageProvider,
    LazyLLMTextProvider,
    OpenAIImageProvider,
    OpenAITextProvider,
)
from services.ai_providers.lazyllm_env import ALLOWED_LAZYLLM_VENDORS
from services.ai_service import AIService
from services.file_parser_service import FileParserService


@dataclass(frozen=True)
class UserAIConfig:
    ai_provider_format: str
    api_key: str
    api_base_url: str | None
    text_model: str
    image_model: str
    image_caption_model: str
    output_language: str
    description_generation_mode: str
    enable_text_reasoning: bool
    text_thinking_budget: int
    enable_image_reasoning: bool
    image_thinking_budget: int
    text_model_source: str | None
    image_model_source: str | None
    image_caption_model_source: str | None
    text_api_key: str | None
    text_api_base_url: str | None
    image_api_key: str | None
    image_api_base_url: str | None
    image_caption_api_key: str | None
    image_caption_api_base_url: str | None
    lazyllm_api_keys: dict[str, str]


def _get_attr(settings: UserSettings, name: str, default: Any):
    value = getattr(settings, name)
    return value if value is not None else default


def _default_global_api_base(provider_format: str) -> str | None:
    if provider_format == "openai":
        return current_app.config.get("OPENAI_API_BASE") or Config.OPENAI_API_BASE
    if provider_format == "anthropic":
        return current_app.config.get("ANTHROPIC_API_BASE") or Config.ANTHROPIC_API_BASE
    if provider_format == "lazyllm" or provider_format in LAZYLLM_VENDORS:
        return None
    return current_app.config.get("GOOGLE_API_BASE") or Config.GOOGLE_API_BASE or None


_MISSING = object()


def _override_value(overrides: dict | None, name: str):
    if not overrides or name not in overrides:
        return _MISSING
    value = overrides[name]
    if isinstance(value, str):
        return value.strip() or None
    return value


def _setting_value(settings: UserSettings, overrides: dict | None, name: str, default: Any = None):
    override = _override_value(overrides, name)
    if override is not _MISSING:
        return override
    value = getattr(settings, name)
    return value if value is not None else default


def _merged_lazyllm_keys(settings: UserSettings, overrides: dict | None) -> dict[str, str]:
    keys = settings.get_lazyllm_api_keys_dict()
    override_keys = _override_value(overrides, "lazyllm_api_keys")
    if isinstance(override_keys, dict):
        keys = {**keys, **{vendor: key for vendor, key in override_keys.items() if key}}
    return keys


def get_user_ai_config(user_id: str, overrides: dict | None = None) -> UserAIConfig:
    settings = UserSettings.get_for_user(user_id)
    provider_format = (_setting_value(
        settings,
        overrides,
        "ai_provider_format",
        current_app.config.get("AI_PROVIDER_FORMAT") or Config.AI_PROVIDER_FORMAT or "gemini",
    ) or "gemini").lower()
    api_key = _setting_value(settings, overrides, "api_key", "")
    api_base = _setting_value(settings, overrides, "api_base_url", _default_global_api_base(provider_format))

    return UserAIConfig(
        ai_provider_format=provider_format,
        api_key=api_key or "",
        api_base_url=api_base,
        text_model=_setting_value(settings, overrides, "text_model", current_app.config.get("TEXT_MODEL", Config.TEXT_MODEL)),
        image_model=_setting_value(settings, overrides, "image_model", current_app.config.get("IMAGE_MODEL", Config.IMAGE_MODEL)),
        image_caption_model=_setting_value(settings, overrides, "image_caption_model", current_app.config.get("IMAGE_CAPTION_MODEL", Config.IMAGE_CAPTION_MODEL)),
        output_language=_setting_value(settings, overrides, "output_language", current_app.config.get("OUTPUT_LANGUAGE", Config.OUTPUT_LANGUAGE)),
        description_generation_mode=_setting_value(settings, overrides, "description_generation_mode", "streaming") or "streaming",
        enable_text_reasoning=bool(_setting_value(settings, overrides, "enable_text_reasoning", False)),
        text_thinking_budget=int(_setting_value(settings, overrides, "text_thinking_budget", 1024)),
        enable_image_reasoning=bool(_setting_value(settings, overrides, "enable_image_reasoning", False)),
        image_thinking_budget=int(_setting_value(settings, overrides, "image_thinking_budget", 1024)),
        text_model_source=_setting_value(settings, overrides, "text_model_source"),
        image_model_source=_setting_value(settings, overrides, "image_model_source"),
        image_caption_model_source=_setting_value(settings, overrides, "image_caption_model_source"),
        text_api_key=_setting_value(settings, overrides, "text_api_key"),
        text_api_base_url=_setting_value(settings, overrides, "text_api_base_url"),
        image_api_key=_setting_value(settings, overrides, "image_api_key"),
        image_api_base_url=_setting_value(settings, overrides, "image_api_base_url"),
        image_caption_api_key=_setting_value(settings, overrides, "image_caption_api_key"),
        image_caption_api_base_url=_setting_value(settings, overrides, "image_caption_api_base_url"),
        lazyllm_api_keys=_merged_lazyllm_keys(settings, overrides),
    )


def _resolve_model_provider(config: UserAIConfig, model_type: str) -> dict:
    source = getattr(config, f"{model_type}_model_source")
    if source:
        source = source.lower()
    if not source:
        source = config.ai_provider_format

    model_api_key = getattr(config, f"{model_type}_api_key")
    model_api_base = getattr(config, f"{model_type}_api_base_url")

    if source == "gemini":
        api_key = model_api_key if model_api_key is not None else config.api_key
        api_base = model_api_base if model_api_base is not None else (config.api_base_url if config.ai_provider_format == "gemini" else current_app.config.get("GOOGLE_API_BASE"))
        if not api_key:
            raise ValueError(f"{model_type} Gemini API key is required")
        return {"format": "gemini", "api_key": api_key, "api_base": api_base}

    if source == "openai":
        api_key = model_api_key if model_api_key is not None else config.api_key
        api_base = model_api_base if model_api_base is not None else (config.api_base_url if config.ai_provider_format == "openai" else current_app.config.get("OPENAI_API_BASE", Config.OPENAI_API_BASE))
        if not api_key:
            raise ValueError(f"{model_type} OpenAI API key is required")
        return {"format": "openai", "api_key": api_key, "api_base": api_base}

    if source == "anthropic":
        api_key = model_api_key if model_api_key is not None else config.api_key
        api_base = model_api_base if model_api_base is not None else (config.api_base_url if config.ai_provider_format == "anthropic" else current_app.config.get("ANTHROPIC_API_BASE", Config.ANTHROPIC_API_BASE))
        if not api_key:
            raise ValueError(f"{model_type} Anthropic API key is required")
        return {"format": "anthropic", "api_key": api_key, "api_base": api_base}

    vendor = source if source in LAZYLLM_VENDORS else None
    if source == "lazyllm":
        vendor = getattr(config, f"{model_type}_model_source") or ("doubao" if model_type == "image" else "deepseek")
    vendor = vendor or source
    if not config.lazyllm_api_keys.get(vendor):
        raise ValueError(f"{model_type} LazyLLM {vendor} API key is required")
    return {"format": "lazyllm", "source": vendor}


def _make_text_provider(provider_config: dict, model: str):
    fmt = provider_config["format"]
    if fmt == "openai":
        return OpenAITextProvider(provider_config["api_key"], provider_config.get("api_base"), model)
    if fmt == "anthropic":
        return AnthropicTextProvider(provider_config["api_key"], provider_config.get("api_base"), model)
    if fmt == "lazyllm":
        return LazyLLMTextProvider(provider_config.get("source") or "deepseek", model)
    return GenAITextProvider(model=model, api_key=provider_config["api_key"], api_base=provider_config.get("api_base"))


def _make_image_provider(provider_config: dict, model: str):
    fmt = provider_config["format"]
    if fmt == "openai":
        return OpenAIImageProvider(provider_config["api_key"], provider_config.get("api_base"), model)
    if fmt == "anthropic":
        return AnthropicImageProvider(provider_config["api_key"], provider_config.get("api_base"), model)
    if fmt == "lazyllm":
        return LazyLLMImageProvider(provider_config.get("source") or "doubao", model)
    return GenAIImageProvider(model=model, api_key=provider_config["api_key"], api_base=provider_config.get("api_base"))


@contextmanager
def user_lazyllm_keys(config: UserAIConfig):
    original_values: dict[str, str | None] = {}
    try:
        for vendor, key in config.lazyllm_api_keys.items():
            vendor_name = (vendor or "").lower()
            if vendor_name not in ALLOWED_LAZYLLM_VENDORS or not key:
                continue
            env_key = f"{vendor_name.upper()}_API_KEY"
            namespace_key = f"BANANA_{vendor_name.upper()}_API_KEY"
            original_values[env_key] = os.environ.get(env_key)
            original_values[namespace_key] = os.environ.get(namespace_key)
            os.environ[env_key] = key
            os.environ[namespace_key] = key
        yield
    finally:
        for env_key, value in original_values.items():
            if value is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = value


def create_user_ai_service(user_id: str, overrides: dict | None = None) -> AIService:
    config = get_user_ai_config(user_id, overrides)
    with user_lazyllm_keys(config):
        text_provider = _make_text_provider(_resolve_model_provider(config, "text"), config.text_model)
        image_provider = _make_image_provider(_resolve_model_provider(config, "image"), config.image_model)
        caption_provider = _make_text_provider(_resolve_model_provider(config, "image_caption"), config.image_caption_model)
    service = AIService(text_provider=text_provider, image_provider=image_provider, caption_provider=caption_provider)
    service.text_model = config.text_model
    service.image_model = config.image_model
    service.caption_model = config.image_caption_model
    service.enable_text_reasoning = config.enable_text_reasoning
    service.text_thinking_budget = config.text_thinking_budget
    service.enable_image_reasoning = config.enable_image_reasoning
    service.image_thinking_budget = config.image_thinking_budget
    return service


def create_user_file_parser(user_id: str, overrides: dict | None = None) -> FileParserService:
    config = get_user_ai_config(user_id, overrides)
    caption_config = _resolve_model_provider(config, "image_caption")
    google_key = caption_config.get("api_key") if caption_config["format"] == "gemini" else ""
    google_base = caption_config.get("api_base") if caption_config["format"] == "gemini" else ""
    openai_key = caption_config.get("api_key") if caption_config["format"] == "openai" else ""
    openai_base = caption_config.get("api_base") if caption_config["format"] == "openai" else ""
    lazyllm_source = caption_config.get("source") if caption_config["format"] == "lazyllm" else ""

    return FileParserService(
        mineru_token=current_app.config.get("MINERU_TOKEN", ""),
        mineru_api_base=current_app.config.get("MINERU_API_BASE", Config.MINERU_API_BASE),
        google_api_key=google_key or "",
        google_api_base=google_base or "",
        openai_api_key=openai_key or "",
        openai_api_base=openai_base or "",
        image_caption_model=config.image_caption_model,
        lazyllm_image_caption_source=lazyllm_source or "",
        lazyllm_api_keys=config.lazyllm_api_keys,
        provider_format=caption_config["format"],
    )
