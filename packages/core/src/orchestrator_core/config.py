from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator"
    redis_url: str = "redis://localhost:6379/0"

    llm_gateway_url: str = "http://localhost:11434/v1"
    llm_gateway_key: str = "ollama"
    llm_default_model: str = "llama3.2"
    embed_model: str = "nomic-embed-text"

    qdrant_url: str = "http://localhost:6333"

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "orchestrator"

    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 1440
    encryption_key: str = "change-me-32-byte-key-for-encryption!!"

    org_rate_limit_per_minute: int = 120

    # LLM HTTP client (corporate proxy / self-signed cert)
    llm_gateway_verify_ssl: bool = True
    llm_gateway_trust_env: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
