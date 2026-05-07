"""Core configuration using Pydantic settings."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings."""

    # App
    APP_NAME: str = "WhatsApp Bot"
    DEBUG: bool = False
    WEB_BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "sqlite:///./whatsapp_bot.db"

    # WhatsApp
    WHATSAPP_VERIFY_TOKEN: str = "your_verify_token_here"
    WHATSAPP_TOKEN: str = "your_whatsapp_access_token"
    WHATSAPP_PHONE_ID: str = "your_phone_number_id"
    WHATSAPP_APP_SECRET: str = ""

    # Admin
    ADMIN_API_KEY: str = "change_this_in_production"

    # AI
    OPENAI_API_KEY: str = ""

    # Google Gemini (for image generation)
    GOOGLE_CLOUD_API_KEY: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    # User Message Queue
    USER_QUEUE_ENABLED: bool = True
    USER_QUEUE_TTL: int = 120
    USER_QUEUE_MAX_SIZE: int = 10

    # Web auth (phone+OTP via WhatsApp, JWT cookie)
    JWT_SECRET: str = "change_this_jwt_secret_in_production"
    JWT_ALG: str = "HS256"
    JWT_TTL_MINUTES: int = 60 * 24 * 7  # 7 days
    OTP_TTL_SECONDS: int = 300  # 5 minutes
    AUTH_COOKIE_NAME: str = "wa_session"

    # Stripe (optional — when unset, billing runs in mock mode for dev)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO: str = ""   # Stripe price id for the Pro plan
    STRIPE_PRICE_MAX: str = ""   # Stripe price id for the Max plan

    # Plan display prices (purely cosmetic on the pricing page)
    PRICE_FREE_LABEL: str = "$0/mo"
    PRICE_PRO_LABEL: str = "$9/mo"
    PRICE_MAX_LABEL: str = "$29/mo"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def billing_mode(self) -> str:
        """``live`` when Stripe is configured, ``mock`` otherwise."""
        return "live" if self.STRIPE_SECRET_KEY else "mock"


settings = Settings()
