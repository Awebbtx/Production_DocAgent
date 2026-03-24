from __future__ import annotations

from pathlib import Path

from it_doc_builder.config import get_settings
from it_doc_builder.models import (
    DeepSeekSettingsResponse,
    DocumentDefaultsResponse,
    EmailSettingsResponse,
    UpdateDeepSeekSettingsRequest,
    UpdateDocumentDefaultsRequest,
    UpdateEmailSettingsRequest,
)


def _env_path() -> Path:
    return Path(".env")


def _read_env_pairs(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        pairs.append((key.strip(), value.strip()))
    return pairs


def _write_env_pairs(path: Path, pairs: list[tuple[str, str]]) -> None:
    rendered = "\n".join(f"{key}={value}" for key, value in pairs) + "\n"
    path.write_text(rendered, encoding="utf-8")


def get_deepseek_settings() -> DeepSeekSettingsResponse:
    settings = get_settings()
    return DeepSeekSettingsResponse(
        deepseek_model=settings.deepseek_model,
        deepseek_base_url=settings.deepseek_base_url,
        api_key_configured=bool(settings.deepseek_api_key),
    )


def update_deepseek_settings(request: UpdateDeepSeekSettingsRequest) -> DeepSeekSettingsResponse:
    path = _env_path()
    pairs = _read_env_pairs(path)
    env_map = {key: value for key, value in pairs}

    env_map["DEEPSEEK_MODEL"] = request.deepseek_model.strip() or "deepseek-chat"
    env_map["DEEPSEEK_BASE_URL"] = request.deepseek_base_url.strip() or "https://api.deepseek.com"
    if request.deepseek_api_key.strip():
        env_map["DEEPSEEK_API_KEY"] = request.deepseek_api_key.strip()

    ordered_keys = [
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
        "OUTPUT_DIR",
        "STYLE_SHEET_PATH",
        "HTML_TEMPLATE_PATH",
        "AUTH_DB_PATH",
        "AUTH_SECRET_KEY",
        "AUTH_SESSION_COOKIE_NAME",
        "AUTH_SESSION_TTL_SECONDS",
        "AUTH_COOKIE_SECURE",
        "BOOTSTRAP_ADMIN_USERNAME",
        "BOOTSTRAP_ADMIN_PASSWORD",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH",
    ]
    rebuilt: list[tuple[str, str]] = []
    for key in ordered_keys:
        if key in env_map:
            rebuilt.append((key, env_map[key]))

    for key, value in env_map.items():
        if key not in {k for k, _ in rebuilt}:
            rebuilt.append((key, value))

    _write_env_pairs(path, rebuilt)
    get_settings.cache_clear()
    return get_deepseek_settings()


def get_document_defaults() -> DocumentDefaultsResponse:
    path = _env_path()
    pairs = _read_env_pairs(path)
    env_map = {key: value for key, value in pairs}
    
    return DocumentDefaultsResponse(
        author=env_map.get("DEFAULT_AUTHOR", "").strip(),
        company_name=env_map.get("DEFAULT_COMPANY_NAME", "").strip(),
        company_logo_url=env_map.get("DEFAULT_COMPANY_LOGO_URL", "").strip(),
    )


def update_document_defaults(request: UpdateDocumentDefaultsRequest) -> DocumentDefaultsResponse:
    path = _env_path()
    pairs = _read_env_pairs(path)
    env_map = {key: value for key, value in pairs}

    env_map["DEFAULT_AUTHOR"] = request.author.strip() if request.author else ""
    env_map["DEFAULT_COMPANY_NAME"] = request.company_name.strip() if request.company_name else ""
    env_map["DEFAULT_COMPANY_LOGO_URL"] = request.company_logo_url.strip() if request.company_logo_url else ""

    ordered_keys = [
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
        "DEFAULT_AUTHOR",
        "DEFAULT_COMPANY_NAME",
        "DEFAULT_COMPANY_LOGO_URL",
        "OUTPUT_DIR",
        "STYLE_SHEET_PATH",
        "HTML_TEMPLATE_PATH",
        "AUTH_DB_PATH",
        "AUTH_SECRET_KEY",
        "AUTH_SESSION_COOKIE_NAME",
        "AUTH_SESSION_TTL_SECONDS",
        "AUTH_COOKIE_SECURE",
        "BOOTSTRAP_ADMIN_USERNAME",
        "BOOTSTRAP_ADMIN_PASSWORD",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH",
    ]
    rebuilt: list[tuple[str, str]] = []
    for key in ordered_keys:
        if key in env_map and env_map[key]:
            rebuilt.append((key, env_map[key]))

    for key, value in env_map.items():
        if key not in {k for k, _ in rebuilt} and value:
            rebuilt.append((key, value))

    _write_env_pairs(path, rebuilt)
    return get_document_defaults()


def get_email_settings() -> EmailSettingsResponse:
    settings = get_settings()
    return EmailSettingsResponse(
        app_base_url=settings.app_base_url,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_use_tls=settings.smtp_use_tls,
        smtp_from_email=settings.smtp_from_email,
        smtp_configured=bool(settings.smtp_host and settings.smtp_from_email and settings.app_base_url),
    )


def update_email_settings(request: UpdateEmailSettingsRequest) -> EmailSettingsResponse:
    path = _env_path()
    pairs = _read_env_pairs(path)
    env_map = {key: value for key, value in pairs}

    env_map["APP_BASE_URL"] = request.app_base_url.strip()
    env_map["SMTP_HOST"] = request.smtp_host.strip()
    env_map["SMTP_PORT"] = str(int(request.smtp_port))
    env_map["SMTP_USERNAME"] = request.smtp_username.strip()
    if request.smtp_password.strip():
        env_map["SMTP_PASSWORD"] = request.smtp_password.strip()
    env_map["SMTP_USE_TLS"] = "true" if request.smtp_use_tls else "false"
    env_map["SMTP_FROM_EMAIL"] = request.smtp_from_email.strip()

    ordered_keys = [
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
        "APP_BASE_URL",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_USE_TLS",
        "SMTP_FROM_EMAIL",
        "DEFAULT_AUTHOR",
        "DEFAULT_COMPANY_NAME",
        "DEFAULT_COMPANY_LOGO_URL",
        "OUTPUT_DIR",
        "STYLE_SHEET_PATH",
        "HTML_TEMPLATE_PATH",
        "AUTH_DB_PATH",
        "AUTH_SECRET_KEY",
        "AUTH_SESSION_COOKIE_NAME",
        "AUTH_SESSION_TTL_SECONDS",
        "AUTH_COOKIE_SECURE",
        "BOOTSTRAP_ADMIN_USERNAME",
        "BOOTSTRAP_ADMIN_PASSWORD",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH",
    ]
    rebuilt: list[tuple[str, str]] = []
    for key in ordered_keys:
        if key in env_map and env_map[key] != "":
            rebuilt.append((key, env_map[key]))

    for key, value in env_map.items():
        if key not in {k for k, _ in rebuilt} and value != "":
            rebuilt.append((key, value))

    _write_env_pairs(path, rebuilt)
    get_settings.cache_clear()
    return get_email_settings()
