from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgresql:passq123@localhost:5432/passq123"
    SECRET_KEY: str = "change-me-in-production"
    
    # Email alert config
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_FROM: str = ""
    ALERT_TO: str = ""  # comma-separated for multiple recipients

    # Health check
    CHECK_INTERVAL_SECONDS: int = 30
    DOWN_ALERT_MINUTES: int = 5

    class Config:
        env_file = ".env"

settings = Settings()
