import os
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env de forma absoluta para garantizar lectura bajo servicios de Windows (NSSM)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


@dataclass
class DatabaseConfig:
    host:     str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port:     int = field(default_factory=lambda: int(os.getenv("DB_PORT", "3306")))
    name:     str = field(default_factory=lambda: os.getenv("DB_NAME", "plex_template"))
    user:     str = field(default_factory=lambda: os.getenv("DB_USER", "root"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def url(self) -> str:
        safe_password = urllib.parse.quote_plus(self.password)
        return (
            f"mysql+pymysql://{self.user}:{safe_password}"
            f"@{self.host}:{self.port}/{self.name}?charset=utf8mb4"
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


def get_plex_db_config() -> DatabaseConfig:
    """Base de datos principal: plex_template (plantillas Plex)."""
    return DatabaseConfig()


def get_kimex_db_config() -> DatabaseConfig:
    """
    Base de datos de producción: kimexproduction (clientes, catálogos).

    Usa las mismas credenciales que plex_template (mismo servidor),
    solo cambia el nombre de la base de datos.
    Sobrescribible con variables KIMEX_DB_* en .env si fuera necesario.
    """
    return DatabaseConfig(
        host     = os.getenv("KIMEX_DB_HOST",     os.getenv("DB_HOST",     "localhost")),
        port     = int(os.getenv("KIMEX_DB_PORT",  os.getenv("DB_PORT",     "3306"))),
        user     = os.getenv("KIMEX_DB_USER",     os.getenv("DB_USER",     "root")),
        password = os.getenv("KIMEX_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
        name     = os.getenv("KIMEX_DB_NAME",     "kimexproduction"),
    )


def get_plex_data_db_config() -> DatabaseConfig:
    """
    Base de datos de datos operativos/precios: plex_data.customer_part_price.

    Usa las mismas credenciales que plex_template (mismo servidor),
    solo cambia el nombre de la base de datos.
    Sobrescribible con variables PLEX_DATA_DB_* en .env si fuera necesario.
    """
    return DatabaseConfig(
        host     = os.getenv("PLEX_DATA_DB_HOST",     os.getenv("DB_HOST",     "localhost")),
        port     = int(os.getenv("PLEX_DATA_DB_PORT",  os.getenv("DB_PORT",     "3306"))),
        user     = os.getenv("PLEX_DATA_DB_USER",     os.getenv("DB_USER",     "root")),
        password = os.getenv("PLEX_DATA_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
        name     = os.getenv("PLEX_DATA_DB_NAME",     "plex_data"),
    )


def _parse_fallback_models(raw: str) -> list[str]:
    """Parsea la lista de fallbacks separada por comas, filtrando vacíos."""
    return [m.strip() for m in raw.split(",") if m.strip()]