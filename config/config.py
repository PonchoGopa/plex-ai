import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "3306")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "plex_ai"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "root"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def url(self) -> str:
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass
class OpenRouterConfig:
    api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )
    model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openrouter/free")
    )
    fallback_models: list[str] = field(
        default_factory=lambda: _parse_fallback_models(
            os.getenv(
                "OPENROUTER_FALLBACK_MODELS",
                "meta-llama/llama-3.3-70b-instruct:free,"
                "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
            )
        )
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("OPENROUTER_MAX_RETRIES", "3"))
    )
    retry_delay: int = field(
        default_factory=lambda: int(os.getenv("OPENROUTER_RETRY_DELAY", "8"))
    )


def _parse_fallback_models(raw: str) -> list[str]:
    """Parsea la lista de fallbacks separada por comas, filtrando vacíos."""
    return [m.strip() for m in raw.split(",") if m.strip()]