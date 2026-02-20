from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FFIS_", env_file=".env", extra="ignore")

    # Siegfried
    siegfried_binary: str = "sf"
    siegfried_server_url: Optional[str] = None  # e.g. http://siegfried:5138

    # Magika
    magika_enabled: bool = True

    # Apache Tika (optional)
    tika_enabled: bool = False
    tika_server_url: Optional[str] = None  # e.g. http://tika:9998

    # Cache
    cache_enabled: bool = True
    cache_db_path: str = "/tmp/ffis_cache.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Registry resolution hierarchy — highest priority first.
    # A PRONOM PUID (specific signature match) overrules a MIME guess.
    registry_hierarchy: list[str] = ["PRONOM", "LOC", "WIKIDATA", "MIME"]

    @field_validator("registry_hierarchy", mode="before")
    @classmethod
    def parse_hierarchy(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [r.strip().upper() for r in v.split(",")]
        return v


settings = Settings()
