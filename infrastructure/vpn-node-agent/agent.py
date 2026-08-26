"""Minimal authenticated WireGuard peer agent; no shell or arbitrary commands."""
import base64, ipaddress, os, subprocess
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="VPN node provisioning agent")
TOKEN = os.environ.get("VPN_NODE_AGENT_TOKEN", "")

class PeerRequest(BaseModel):
    operation: str
    public_key: str = Field(min_length=44, max_length=44)
    assigned_ip: str | None = None

def check_key(key: str) -> None:
    try:
        if len(base64.b64decode(key, validate=True)) != 32: raise ValueError
    except Exception as exc: raise HTTPException(422, "invalid public key") from exc

@app.post("/v1/peers")
def peer(request: PeerRequest, authorization: str | None = Header(default=None)) -> dict[str, str]:
    if not TOKEN or authorization != f"Bearer {TOKEN}": raise HTTPException(401, "invalid agent credentials")
    check_key(request.public_key)
    if request.operation not in {"add", "remove"}: raise HTTPException(422, "unsupported operation")
    if request.assigned_ip is not None:
        try: ipaddress.ip_interface(request.assigned_ip)
        except ValueError as exc: raise HTTPException(422, "invalid assigned ip") from exc
    args = ["wg", "set", "wg0"]
    if request.operation == "add": args += ["peer", request.public_key, "allowed-ips", request.assigned_ip or ""]
    else: args += ["peer", request.public_key, "remove"]
    subprocess.run(args, shell=False, check=True, capture_output=True, timeout=5)
    return {"status": request.operation}
