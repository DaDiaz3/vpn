import ipaddress
import re
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

class ProvisionRequest(BaseModel):
    server_id: UUID
    public_key: str = Field(min_length=44, max_length=44)
    @field_validator("public_key")
    @classmethod
    def valid_wireguard_key(cls, value: str) -> str:
        import base64
        try:
            if len(base64.b64decode(value, validate=True)) != 32:
                raise ValueError
        except Exception as exc:
            raise ValueError("public_key must be a WireGuard base64 key") from exc
        return value

class ProvisionResponse(BaseModel):
    credential_id: UUID
    server: dict[str, object]
    client: dict[str, str]
    dns: list[str]
    allowed_ips: list[str]
    persistent_keepalive: int = 25

def validate_server_network(value: str) -> str:
    network = ipaddress.ip_network(value, strict=True)
    if network.version != 4 or network.prefixlen >= 31: raise ValueError("network_cidr must be IPv4 /30 or larger")
    return value

def validate_endpoint(value: str) -> str:
    match = re.fullmatch(r"(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\]):([0-9]{1,5})", value)
    if not match or not 1 <= int(match.group(1)) <= 65535: raise ValueError("endpoint must be host:port")
    return value
