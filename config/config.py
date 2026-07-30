import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    name: str

    @property
    def connection_url(self) -> str:
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    base_url: str
    model: str
    fallback_models: list[str] = field(default_factory=list)


def get_database_config() -> DatabaseConfig:
    return DatabaseConfig(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        name=os.getenv("DB_NAME", "plex_template"),
    )


def get_openrouter_config() -> OpenRouterConfig:
    """
    Variables esperadas:
      OPENROUTER_API_KEY (obligatoria)
      OPENROUTER_BASE_URL (opcional)
      OPENROUTER_MODEL (modelo principal)
      OPENROUTER_FALLBACK_MODELS (opcional, separados por coma;
        se intentan en orden si el modelo principal sigue
        saturado/rate-limited después de sus reintentos)
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY no está definida. "
            "Agrégala a tu archivo .env (ver .env.example)."
        )

    fallback_raw = os.getenv("OPENROUTER_FALLBACK_MODELS", "")
    fallback_models = [m.strip() for m in fallback_raw.split(",") if m.strip()]

    return OpenRouterConfig(
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free"),
        fallback_models=fallback_models,
    )