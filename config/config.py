import os
from dataclasses import dataclass
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


def get_database_config() -> DatabaseConfig:
    """
    Lee la configuración de conexión desde variables de entorno,
    con valores por defecto solo para desarrollo local.

    Variables esperadas:
      DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    """
    return DatabaseConfig(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        name=os.getenv("DB_NAME", "plex_template"),
    )