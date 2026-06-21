from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://attribute_ai:attribute_ai@localhost:5432/attribute_ai"

    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024

    fuzzy_auto_threshold: float = 93.0
    semantic_auto_threshold: float = 0.86
    semantic_review_threshold: float = 0.74
    semantic_gap_threshold: float = 0.04

    max_semantic_candidates: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
