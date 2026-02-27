from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    model_config = {"extra": "allow"}

    log_level: str = "INFO"
    """Log level for the application. Default is 'INFO'."""

    database_url: PostgresDsn
    """Database connection URL. Example: postgresql://user:password@localhost:5432/mydb"""

    oidc_authority: str
    """https://auth.example.com/application/o/myapp/"""

    oidc_client_id: str
    """Client ID"""

    cors_allowed_origins: list[str] = ["http://localhost:5173"]

    root_path: str = ""


settings = Settings(_env_prefix="APP_", _env_file=".env")
