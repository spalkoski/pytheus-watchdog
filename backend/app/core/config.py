import os
import yaml
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional


class Settings(BaseSettings):
    # App settings
    app_name: str = "Pytheus Watchdog"
    app_env: str = "production"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/watchdog.db"

    # Security
    secret_key: str
    api_token_secret: str
    admin_username: str = "admin"
    admin_password: str

    # Slack
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#monitoring"

    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Email
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    alert_email: Optional[str] = None

    # AI (Phase 3)
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    ai_triage_enabled: bool = False

    # Twilio (Phase 4)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    twilio_to_number: Optional[str] = None

    # Timezone
    tz: str = "UTC"

    class Config:
        env_file = ".env"
        case_sensitive = False


def load_watchdog_config() -> Dict[str, Any]:
    """Load the watchdog.yaml configuration file."""
    config_path = Path("config/watchdog.yaml")

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Replace environment variables in config
    config_str = yaml.dump(config)
    for key, value in os.environ.items():
        config_str = config_str.replace(f"${{{key}}}", value)

    return yaml.safe_load(config_str)


# Global settings instance
settings = Settings()
watchdog_config = load_watchdog_config()
