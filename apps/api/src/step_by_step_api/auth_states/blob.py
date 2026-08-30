from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from step_by_step_api.auth_states.domains import registrable_domain


class Cookie(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str
    value: str
    domain: str
    path: str = "/"
    expires: float | None = None
    http_only: bool = Field(default=False, alias="httpOnly")
    secure: bool = False
    same_site: str | None = Field(default=None, alias="sameSite")
    partition_key: Any | None = Field(default=None, alias="partitionKey")


class StorageItem(BaseModel):
    name: str
    value: str


class OriginStorage(BaseModel):
    origin: str
    local_storage: list[StorageItem]


class SessionStorage(BaseModel):
    origin: str
    items: list[StorageItem]


class AuthStateBlob(BaseModel):
    domain: str
    cookies: list[Cookie]
    origins: list[OriginStorage]
    session_storage: list[SessionStorage]

    @field_validator("domain")
    @classmethod
    def domain_is_registrable(cls, value: str) -> str:
        domain = registrable_domain(value)
        if domain != value.rstrip(".").lower():
            raise ValueError("domain must be a registrable domain")
        return domain
