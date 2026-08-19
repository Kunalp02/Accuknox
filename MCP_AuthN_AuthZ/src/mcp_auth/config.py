from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MCP AuthN AuthZ"
    api_host: str = "0.0.0.0"
    api_port: int = 8100
    base_url: str = "http://localhost:8100"
    cors_origins: str = "http://localhost:5173"

    database_url: str = "sqlite+aiosqlite:///./mcp_auth.db"

    jwt_secret: str = "dev-secret-change-in-production"
    jwt_expire_minutes: int = 1440
    encryption_key: str = "dev-encryption-key-change-me"

    mcp_server_resource_uri: str = "http://localhost:8100/mcp"
    mcp_oauth_issuer: str = "http://localhost:8100"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
