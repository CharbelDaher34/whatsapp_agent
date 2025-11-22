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
    
    # Admin
    ADMIN_API_KEY: str = "change_this_in_production"
    
    # AI
    OPENAI_API_KEY: str = ""
    
    # Google Gemini (for Image Generation)
    GOOGLE_CLOUD_API_KEY: str = ""
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
