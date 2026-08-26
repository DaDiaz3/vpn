import base64
import ipaddress
import os
from datetime import UTC, datetime
from uuid import UUID
import httpx
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Subscription, SubscriptionStatus, User, UserStatus, VPNCredential, VPNCredentialStatus, VPNServer, VPNServerStatus
from app.services.trials import AccessState, TrialService

class ProvisioningError(Exception): pass
class AccessDeniedError(Exception): pass
class CapacityExhaustedError(Exception): pass
class NodeUnavailableError(Exception): pass

def validate_public_key(value: str) -> bool:
    try: return len(base64.b64decode(value, validate=True)) == 32 and len(value) == 44
    except Exception: return False

async def provision_peer(server: VPNServer, public_key: str, assigned_ip: str) -> None:
    url = os.getenv("VPN_NODE_AGENT_URL", "").rstrip("/")
    if not url: return
    token = os.getenv("VPN_NODE_AGENT_TOKEN")
    if not token: raise NodeUnavailableError("node agent authentication is not configured")
    try:
        async with httpx.AsyncClient(timeout=5.0, verify=True) as client:
            response = await client.post(f"{url}/v1/peers", json={"operation": "add", "public_key": public_key, "assigned_ip": assigned_ip}, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
    except (httpx.HTTPError, TimeoutError) as exc:
        raise NodeUnavailableError from exc

async def remove_peer(server: VPNServer, public_key: str, assigned_ip: str | None) -> None:
    url = os.getenv("VPN_NODE_AGENT_URL", "").rstrip("/")
    if not url: return
    token = os.getenv("VPN_NODE_AGENT_TOKEN")
    if not token: raise NodeUnavailableError
    try:
        async with httpx.AsyncClient(timeout=5.0, verify=True) as client:
            response = await client.post(f"{url}/v1/peers", json={"operation": "remove", "public_key": public_key, "assigned_ip": assigned_ip}, headers={"Authorization": f"Bearer {token}"})
            if response.status_code not in (200, 404): response.raise_for_status()
    except (httpx.HTTPError, TimeoutError) as exc: raise NodeUnavailableError from exc

class VPNProvisioningService:
    def __init__(self, session: AsyncSession): self.session = session
    async def _access_allowed(self, user: User) -> bool:
        if user.status is not UserStatus.ACTIVE: return False
        subscribed = (await self.session.execute(select(Subscription.id).where(Subscription.user_id == user.id, Subscription.status == SubscriptionStatus.ACTIVE, (Subscription.expires_at.is_(None) | (Subscription.expires_at > text("now()")))))).scalar_one_or_none() is not None
        return TrialService().determine_access_state(user, is_subscribed=subscribed) in (AccessState.TRIAL_ACTIVE, AccessState.SUBSCRIBED)
    async def provision(self, user: User, server_id: UUID, public_key: str) -> VPNCredential:
        if not await self._access_allowed(user): raise AccessDeniedError
        if not validate_public_key(public_key): raise ProvisioningError("invalid public key")
        server = await self.session.get(VPNServer, server_id)
        if server is None or server.status not in (VPNServerStatus.ONLINE, VPNServerStatus.DEGRADED): raise ProvisioningError("server unavailable")
        existing = (await self.session.execute(select(VPNCredential).where(VPNCredential.user_id == user.id, VPNCredential.server_id == server.id, VPNCredential.public_key == public_key, VPNCredential.status == VPNCredentialStatus.ACTIVE))).scalar_one_or_none()
        if existing: return existing
        network = ipaddress.ip_network(server.network_cidr, strict=False)
        async with self.session.begin_nested():
            await self.session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(server.id)})
            used = {row[0] for row in (await self.session.execute(select(VPNCredential.assigned_ip).where(VPNCredential.server_id == server.id, VPNCredential.status == VPNCredentialStatus.ACTIVE))).all()}
            hosts = iter(network.hosts())
            next(hosts, None)  # reserve the node's first host address (10.20.0.1)
            assigned = next((str(ip) for ip in hosts if str(ip) not in used), None)
            if assigned is None: raise CapacityExhaustedError
            credential = VPNCredential(user_id=user.id, server_id=server.id, public_key=public_key, assigned_ip=assigned)
            self.session.add(credential)
            try: await self.session.flush()
            except IntegrityError:
                await self.session.rollback()
                existing = (await self.session.execute(select(VPNCredential).where(VPNCredential.user_id == user.id, VPNCredential.server_id == server.id, VPNCredential.public_key == public_key, VPNCredential.status == VPNCredentialStatus.ACTIVE))).scalar_one_or_none()
                if existing: return existing
                raise CapacityExhaustedError from None
        try: await provision_peer(server, public_key, f"{assigned}/32")
        except NodeUnavailableError:
            await self.session.delete(credential); await self.session.flush(); raise
        return credential
    async def revoke(self, user: User, credential_id: UUID) -> bool:
        credential = await self.session.get(VPNCredential, UUID(str(credential_id)))
        if credential is None or credential.user_id != user.id: raise ProvisioningError("credential not found")
        if credential.status is VPNCredentialStatus.REVOKED: return False
        server = await self.session.get(VPNServer, credential.server_id)
        credential.status = VPNCredentialStatus.REVOKED
        credential.revoked_at = datetime.now(UTC)
        await self.session.flush()
        if server:
            try:
                await remove_peer(server, credential.public_key, f"{credential.assigned_ip}/32" if credential.assigned_ip else None)
            except NodeUnavailableError:
                credential.node_sync_pending = True
                await self.session.flush()
        return True

    async def reconcile_pending(self) -> int:
        pending = list((await self.session.execute(select(VPNCredential).where(VPNCredential.status == VPNCredentialStatus.REVOKED, VPNCredential.node_sync_pending.is_(True)))).scalars())
        cleared = 0
        for credential in pending:
            server = await self.session.get(VPNServer, credential.server_id)
            try:
                if server: await remove_peer(server, credential.public_key, f"{credential.assigned_ip}/32" if credential.assigned_ip else None)
            except NodeUnavailableError:
                continue
            credential.node_sync_pending = False
            cleared += 1
        await self.session.flush()
        return cleared
