from dataclasses import dataclass


@dataclass
class AuthContext:
    org_id: str
    user_id: str | None = None
    role: str | None = None
    api_key_id: str | None = None
    scopes: list[str] | None = None

    @property
    def is_api_key(self) -> bool:
        return self.api_key_id is not None

    @property
    def principal_type(self) -> str:
        return "api_key" if self.is_api_key else "user"

    @property
    def principal_id(self) -> str:
        if self.api_key_id:
            return self.api_key_id
        if self.user_id:
            return self.user_id
        return "anonymous"
