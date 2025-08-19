from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://username:password@hostname/dbname"
    google_ai_api_key: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings()