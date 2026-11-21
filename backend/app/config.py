from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=("settings_",))

    database_url: str = "postgresql+psycopg://ecd:ecd@db:5432/ecd"
    secret_key: str = "ganti-dengan-secret-acak"
    token_hours: int = 12

    admin_username: str = "admin"
    admin_password: str = "admin123"

    # zona waktu `dtsrv` di file Navita; disimpan sebagai UTC, ditampilkan WIB
    source_tz: str = "Asia/Jakarta"
    display_tz: str = "Asia/Jakarta"

    inbox_dir: str = "/data/inbox"
    upload_dir: str = "/data/uploads"
    model_dir: str = "/data/models"
    report_dir: str = "/data/reports"
    watch_interval_s: int = 60
    watch_enabled: bool = True

    # ambang turunan state
    flow_min_gpm: float = 50.0
    rpm_min: float = 5.0
    on_bottom_ft: float = 1.0
    block_move_ft_s: float = 0.05
    resample_s: int = 30

    # AI narasi (opsional, hanya ringkasan hasil yang dikirim)
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"

    # publikasi: CORS hanya bila frontend beda origin (default: tidak ada, karena frontend & API satu domain)
    cors_origins: str = ""
    docs_enabled: bool = True  # /api/docs; matikan (false) di server publik


@lru_cache
def get_settings() -> Settings:
    return Settings()
