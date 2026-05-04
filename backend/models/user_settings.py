"""Per-user AI settings model."""
import json
from datetime import datetime, timezone

from . import db


class UserSettings(db.Model):
    """Stores user-owned LLM provider configuration."""

    __tablename__ = "user_settings"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), primary_key=True)
    ai_provider_format = db.Column(db.String(20), nullable=True)
    api_base_url = db.Column(db.String(500), nullable=True)
    api_key = db.Column(db.String(500), nullable=True)
    text_model = db.Column(db.String(100), nullable=True)
    image_model = db.Column(db.String(100), nullable=True)
    image_caption_model = db.Column(db.String(100), nullable=True)
    output_language = db.Column(db.String(10), nullable=True)
    description_generation_mode = db.Column(db.String(20), nullable=True)
    enable_text_reasoning = db.Column(db.Boolean, nullable=False, default=False)
    text_thinking_budget = db.Column(db.Integer, nullable=False, default=1024)
    enable_image_reasoning = db.Column(db.Boolean, nullable=False, default=False)
    image_thinking_budget = db.Column(db.Integer, nullable=False, default=1024)
    text_model_source = db.Column(db.String(50), nullable=True)
    image_model_source = db.Column(db.String(50), nullable=True)
    image_caption_model_source = db.Column(db.String(50), nullable=True)
    lazyllm_api_keys = db.Column(db.Text, nullable=True)
    text_api_key = db.Column(db.String(500), nullable=True)
    text_api_base_url = db.Column(db.String(500), nullable=True)
    image_api_key = db.Column(db.String(500), nullable=True)
    image_api_base_url = db.Column(db.String(500), nullable=True)
    image_caption_api_key = db.Column(db.String(500), nullable=True)
    image_caption_api_base_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="settings")

    def _val(self, attr: str, defaults: dict):
        value = getattr(self, attr)
        return value if value is not None else defaults.get(attr)

    def get_lazyllm_api_keys_dict(self) -> dict:
        if not self.lazyllm_api_keys:
            return {}
        try:
            parsed = json.loads(self.lazyllm_api_keys)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _get_lazyllm_api_keys_info(self, raw=None) -> dict:
        data = raw if raw is not None else self.lazyllm_api_keys
        if not data:
            return {}
        try:
            keys = json.loads(data)
            if not isinstance(keys, dict):
                return {}
            return {vendor: len(key) for vendor, key in keys.items() if key}
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_dict(self):
        api_key = self.api_key

        return {
            "id": 1,
            "user_id": self.user_id,
            "api_key_length": len(api_key) if api_key else 0,
            "output_language": self.output_language,
            "mineru_token_length": 0,
            "baidu_api_key_length": 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def get_for_user(user_id: str):
        settings = UserSettings.query.filter_by(user_id=user_id).first()
        if settings is None:
            settings = UserSettings(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings

    def __repr__(self):
        return f"<UserSettings user_id={self.user_id}>"
