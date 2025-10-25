"""
Configuration management for EchoDiary
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    app_name: str = "EchoDiary"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./echodiary.db"
    
    # Upstash Redis
    upstash_redis_url: str
    upstash_redis_token: str
    
    # OpenAI (Required - we use this directly)
    openai_api_key: str
    
    # These are now OPTIONAL - Layercode handles them
    deepgram_api_key: str = ""
    rime_api_key: str = ""
    rime_api_url: str = "https://api.rime.ai/v1"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_webhook_base_url: str = ""
    openai_model: str = "gpt-4-turbo-preview"
    openai_max_tokens: int = 100
    openai_temperature: float = 0.7
    
    # Layercode (Required for web calling)
    layercode_api_key: str = ""
    layercode_agent_id: str = ""  # Your Layercode agent ID for web calling
    
    # Session Settings
    session_ttl_seconds: int = 7200  # 2 hours
    context_turns_limit: int = 3
    
    # Mood Scoring
    mood_negative_threshold: float = 3.0
    checkin_delay_hours: int = 24
    
    # Audio Storage
    audio_storage_path: str = "./audio_recordings"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

