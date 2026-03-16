from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Required
    SECRET_KEY: str
    FERNET_KEY: str
    BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "sqlite:///data/family.db"
    DATA_DIR: str = "/data"

    # Facebook OAuth
    FB_ENABLED: bool = False
    FB_APP_ID: str = ""
    FB_APP_SECRET: str = ""

    # Admin
    ADMIN_EMAILS: str = ""
    REQUIRE_APPROVAL: bool = False

    # SMTP for magic links
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = ""

    # Envelope API (alternative to SMTP)
    ENVELOPE_API_URL: str = ""
    ENVELOPE_API_KEY: str = ""
    ENVELOPE_WEBHOOK_SECRET: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def admin_email_list(self) -> list[str]:
        if not self.ADMIN_EMAILS:
            return []
        return [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]


def get_settings() -> Settings:
    return Settings()
