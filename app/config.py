from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    openai_api_key: str
    openai_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"
    monitoring_mode: str = "demo"
    monitoring_input_mode: str = "manifest"
    monitoring_catalog_path: str = "config/products.real.json"
    monitoring_screenshot_manifest_path: str = "config/screenshots.manifest.json"
    monitoring_screenshot_root: str = "."
    monitoring_roi_profiles_path: str = "config/roi_profiles.json"
    monitoring_phrase_sets_path: str = "config/phrase_sets.json"
    monitoring_artifact_root: str = "output/artifacts"
    monitoring_database_url: str = ""
    monitoring_scheduler_enabled: bool = False
    monitoring_scan_interval_seconds: int = 3600
    monitoring_max_concurrency: int = 3
    monitoring_scan_timeout_seconds: float = 120.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
