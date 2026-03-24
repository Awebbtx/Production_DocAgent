from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = Field(default="deepseek", alias="LLM_PROVIDER")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    output_dir: Path = Field(default=Path("output"), alias="OUTPUT_DIR")
    style_sheet_path: Path = Field(default=Path("styles/report.css"), alias="STYLE_SHEET_PATH")
    html_template_path: Path = Field(default=Path("templates/report.html.j2"), alias="HTML_TEMPLATE_PATH")
    auth_db_path: Path = Field(default=Path("output/auth.db"), alias="AUTH_DB_PATH")
    auth_secret_key: str = Field(default="change-me-in-production", alias="AUTH_SECRET_KEY")
    auth_session_cookie_name: str = Field(default="docagent_session", alias="AUTH_SESSION_COOKIE_NAME")
    auth_session_ttl_seconds: int = Field(default=43200, alias="AUTH_SESSION_TTL_SECONDS")
    auth_cookie_secure: bool = Field(default=True, alias="AUTH_COOKIE_SECURE")
    bootstrap_admin_username: str = Field(default="", alias="BOOTSTRAP_ADMIN_USERNAME")
    bootstrap_admin_password: str = Field(default="", alias="BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_admin_credentials_path: Path = Field(
        default=Path("output/bootstrap-admin-credentials.txt"),
        alias="BOOTSTRAP_ADMIN_CREDENTIALS_PATH",
    )
    app_base_url: str = Field(default="http://127.0.0.1:8000", alias="APP_BASE_URL")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_from_email: str = Field(default="", alias="SMTP_FROM_EMAIL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.auth_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.bootstrap_admin_credentials_path.parent.mkdir(parents=True, exist_ok=True)
    return settings