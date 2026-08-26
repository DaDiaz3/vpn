from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.db.models import VPNServerStatus
def _valid_wireguard_key(value: str) -> bool:
    import base64
    try: return len(value) == 44 and len(base64.b64decode(value, validate=True)) == 32
    except Exception: return False


class ServerPublic(BaseModel):
    id: UUID
    name: str
    country: str
    city: str
    status: VPNServerStatus
    latency_ms: float | None
    load_percent: Decimal | None
    active_users: int | None


class ServerListResponse(BaseModel):
    servers: list[ServerPublic]


class AdminServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=2, max_length=2)
    city: str = Field(min_length=1, max_length=100)
    hostname: str = Field(min_length=1, max_length=255)
    capacity: int = Field(ge=1)
    node_secret: SecretStr = Field(min_length=32, max_length=512, json_schema_extra={"writeOnly": True})
    network_cidr: str = "10.20.0.0/24"
    endpoint: str = ""
    wireguard_public_key: str = ""
    dns: str = "1.1.1.1"

    @field_validator("network_cidr")
    @classmethod
    def network_valid(cls, value: str) -> str:
        import ipaddress
        network = ipaddress.ip_network(value, strict=True)
        if network.version != 4 or network.prefixlen >= 31: raise ValueError("network_cidr must be IPv4 /30 or larger")
        return value

    @field_validator("endpoint")
    @classmethod
    def endpoint_valid(cls, value: str) -> str:
        if value:
            host, sep, port = value.rpartition(":")
            if not sep or not host or not port.isdigit() or not 1 <= int(port) <= 65535: raise ValueError("endpoint must be host:port")
        return value

    @field_validator("wireguard_public_key")
    @classmethod
    def key_valid(cls, value: str) -> str:
        if value and not _valid_wireguard_key(value): raise ValueError("invalid WireGuard public key")
        return value

    @field_validator("dns")
    @classmethod
    def dns_valid(cls, value: str) -> str:
        import ipaddress
        for item in value.split(","):
            ipaddress.ip_address(item.strip())
        return value

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.upper()


class AdminServerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    capacity: int | None = Field(default=None, ge=1)
    status: VPNServerStatus | None = None
    network_cidr: str | None = None
    endpoint: str | None = None
    wireguard_public_key: str | None = None
    dns: str | None = None

    @field_validator("country")
    @classmethod
    def normalize_optional_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class AdminServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    country: str
    city: str
    hostname: str
    status: VPNServerStatus
    capacity: int
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NodeHeartbeatRequest(BaseModel):
    server_id: UUID
    timestamp: datetime
    cpu_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    memory_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    bandwidth_in: int = Field(ge=0)
    bandwidth_out: int = Field(ge=0)
    active_users: int = Field(ge=0)
    packet_loss_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    latency_ms: Decimal = Field(ge=0, max_digits=10, decimal_places=2)

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class HeartbeatResponse(BaseModel):
    status: VPNServerStatus
