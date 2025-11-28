"""Core configuration using Pydantic settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Get the project root directory (parent of app/)
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    """Application settings."""
    
    # App
    APP_NAME: str = "WhatsApp Bot"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///./whatsapp_bot.db"
    
    # WhatsApp
    WHATSAPP_VERIFY_TOKEN: str = "your_verify_token_here"
    WHATSAPP_TOKEN: str = "your_whatsapp_access_token"
    WHATSAPP_PHONE_ID: str = "your_phone_number_id"
    WHATSAPP_APP_SECRET: str = ""  # For webhook signature verification
    
    # Admin
    ADMIN_API_KEY: str = "change_this_in_production"
    
    # AI
    OPENAI_API_KEY: str = ""
    
    # Google Gemini (for Image Generation)
    GOOGLE_CLOUD_API_KEY: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # User Message Queue
    USER_QUEUE_ENABLED: bool = True
    USER_QUEUE_TTL: int = 120  # seconds - lock expires after this time
    USER_QUEUE_MAX_SIZE: int = 10  # max messages queued per user
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
