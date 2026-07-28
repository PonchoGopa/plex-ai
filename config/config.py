import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Carga las variables definidas en .env al entorno del proceso.
# Si .env no existe (ej. en producción, donde las variables ya
# están seteadas a nivel de sistema/contenedor), no falla: simplemente
# no sobreescribe nada.
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


def get_database_config() -> DatabaseConfig:
    """
    Variables esperadas: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    """
    return DatabaseConfig(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        name=os.getenv("DB_NAME", "plex_template"),
    )


def get_openrouter_config() -> OpenRouterConfig:
    """
    Variables esperadas: OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

    OPENROUTER_API_KEY es obligatoria: si no está seteada, fallamos
    de inmediato con un mensaje claro, en vez de dejar que falle más
    adelante con un error 401 confuso desde la API.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY no está definida. "
            "Agrégala a tu archivo .env (ver .env.example)."
        )

    return OpenRouterConfig(
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
    )