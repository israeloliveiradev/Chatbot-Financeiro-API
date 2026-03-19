from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str
    
    database_url: str
    redis_url: str
    
    gemini_api_key: str
    
    evolution_base_url: str
    evolution_instance: str
    evolution_api_key: str
    
    internal_api_key: str

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore",
        env_ignore_empty=True # Ignorar se for vazio
    )

settings = Settings()
