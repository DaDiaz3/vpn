"""Stage 5 contract and node-agent hardening tests."""
import ast
import base64
from pathlib import Path
import pytest
import asyncio
from datetime import UTC, datetime, timedelta
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.db.models import User, UserStatus, VPNServer, VPNServerStatus, NodeCredential
from app.core.security import hash_password
from app.services.vpn_provisioning import VPNProvisioningService
from tests.test_auth import run_database_test
from app.services.vpn_provisioning import validate_public_key
from app.schemas.servers import AdminServerCreate

VALID_KEY = "A" * 43 + "="

def test_valid_wireguard_key_is_accepted():
    assert validate_public_key(VALID_KEY) is True

@pytest.mark.parametrize("key", ["short", "A;whoami", "../etc/passwd", "A" * 44])
def test_invalid_wireguard_keys_rejected(key):
    assert validate_public_key(key) is False

@pytest.mark.parametrize("network", ["10.20.0.0/31", "10.20.0.0/32", "not-a-network"])
def test_invalid_network_rejected(network):
    with pytest.raises(Exception): AdminServerCreate(name="n", country="JP", city="Tokyo", hostname="h", capacity=1, node_secret="x"*32, network_cidr=network)

@pytest.mark.parametrize("endpoint", ["host:0", "host:65536", "host", "host;1"])
def test_invalid_endpoint_rejected(endpoint):
    with pytest.raises(Exception): AdminServerCreate(name="n", country="JP", city="Tokyo", hostname="h", capacity=1, node_secret="x"*32, endpoint=endpoint)

def test_node_agent_has_no_generic_execution():
    source = Path(__file__).parents[2] / "infrastructure/vpn-node-agent/agent.py"
    tree = ast.parse(source.read_text())
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {"system", "eval", "exec"} for n in ast.walk(tree))
    runs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "run"]
    assert runs and all(any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is False for k in n.keywords) for n in runs)

def test_node_agent_rejects_injection():
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("vpn_agent", Path(__file__).parents[2] / "infrastructure/vpn-node-agent/agent.py"); mod = module_from_spec(spec); spec.loader.exec_module(mod)
    mod.TOKEN = "test-token"
    with pytest.raises(Exception): mod.peer(mod.PeerRequest(operation="add", public_key="A"*43+"=", assigned_ip="10.20.0.2;whoami"), "Bearer test-token")

def test_real_postgres_concurrent_ip_allocation():
    async def scenario(factory: async_sessionmaker[AsyncSession]):
        async with factory.begin() as session:
            server = VPNServer(name="n", country="JP", city="T", hostname="concurrent", capacity=20, status=VPNServerStatus.ONLINE, network_cidr="10.20.0.0/28")
            session.add(server); await session.flush(); sid = server.id
            users = []
            for i in range(5):
                user = User(email=f"c{i}@e.test", password_hash=hash_password("password"), status=UserStatus.ACTIVE, trial_started_at=datetime.now(UTC), trial_ends_at=datetime.now(UTC)+timedelta(days=1)); session.add(user); users.append(user)
            await session.flush(); ids = [(u.id, sid) for u in users]
        async def one(i):
            async with factory() as s:
                u = await s.get(User, ids[i][0]); c = await VPNProvisioningService(s).provision(u, sid, base64.b64encode(bytes([i+1])*32).decode())
                await s.commit(); return c.assigned_ip
        ips = await asyncio.gather(*(one(i) for i in range(5)))
        assert len(set(ips)) == 5
    run_database_test(scenario)
