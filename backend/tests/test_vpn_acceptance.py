import base64
import uuid
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from app.db.models import User, UserStatus, VPNCredential, VPNCredentialStatus, VPNServer, VPNServerStatus
from app.core.security import JWTService, hash_password
from app.core.config import get_auth_settings
from app.services.vpn_provisioning import NodeUnavailableError
from tests.test_auth import api_client, run_database_test
from app.db.base import Base

def key(n=1): return base64.b64encode(bytes([n])*32).decode()
async def setup(factory, *, status=UserStatus.ACTIVE, trial_days=1, server_status=VPNServerStatus.ONLINE, network="10.20.0.0/29", admin=False):
    async with factory.begin() as s:
        u=User(email=f"u{uuid.uuid4().hex}@e.test",password_hash=hash_password("password"),status=status,is_admin=admin,trial_started_at=datetime.now(UTC),trial_ends_at=datetime.now(UTC)+timedelta(days=trial_days)); s.add(u)
        sv=VPNServer(name="n",country="JP",city="T",hostname=f"h{uuid.uuid4().hex}",capacity=20,status=server_status,network_cidr=network); s.add(sv); await s.flush()
        return u,sv,JWTService(get_auth_settings()).create_access_token(u.id)

def test_active_trial_can_provision():
    async def scenario(f):
        u,sv,t=await setup(f)
        async with api_client(f) as c:
            r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})
        assert r.status_code==200 and r.json()['client']['address'].startswith('10.20.0.')
    run_database_test(scenario)

def test_expired_trial_cannot_provision():
    async def scenario(f):
        _,sv,t=await setup(f,trial_days=-1)
        async with api_client(f) as c: r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})
        assert r.status_code==403
    run_database_test(scenario)

def test_suspended_user_cannot_provision():
    async def scenario(f):
        _,sv,t=await setup(f,status=UserStatus.SUSPENDED)
        async with api_client(f) as c: r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})
        assert r.status_code==401
    run_database_test(scenario)

def test_unavailable_server_rejected():
    async def scenario(f):
        _,sv,t=await setup(f,server_status=VPNServerStatus.OFFLINE)
        async with api_client(f) as c: r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})
        assert r.status_code==400
    run_database_test(scenario)

def test_maintenance_server_cannot_be_provisioned():
    async def scenario(f):
        _,sv,t=await setup(f,server_status=VPNServerStatus.MAINTENANCE)
        async with api_client(f) as c: r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})
        assert r.status_code==400
        async with f() as s: assert (await s.execute(select(VPNCredential))).all()==[]
    run_database_test(scenario)

def test_invalid_public_key_rejected():
    async def scenario(f):
        _,sv,t=await setup(f)
        async with api_client(f) as c: r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':'bad'})
        assert r.status_code==422
    run_database_test(scenario)

def test_provision_is_idempotent():
    async def scenario(f):
        _,sv,t=await setup(f)
        async with api_client(f) as c:
            a=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()}); b=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})
        assert a.json()['credential_id']==b.json()['credential_id']
    run_database_test(scenario)

def test_capacity_exhaustion():
    async def scenario(f):
        _,sv,t=await setup(f,network='10.20.0.0/30')
        async with api_client(f) as c:
            assert (await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})).status_code==200
            r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key(2)})
        assert r.status_code==409
    run_database_test(scenario)

def test_public_response_has_no_secrets():
    async def scenario(f):
        _,sv,t=await setup(f)
        async with api_client(f) as c: r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})
        body=r.text.lower(); assert 'private' not in body and 'token' not in body and 'secret' not in body
    run_database_test(scenario)

def test_node_failure_rolls_back(monkeypatch):
    async def fail(*a,**k): raise NodeUnavailableError
    monkeypatch.setattr('app.services.vpn_provisioning.provision_peer',fail)
    async def scenario(f):
        _,sv,t=await setup(f)
        async with api_client(f) as c: r=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()})
        assert r.status_code==503
        async with f() as s: assert (await s.execute(select(VPNCredential))).all()==[]
    run_database_test(scenario)

def test_user_cannot_revoke_another_users_credential():
    async def scenario(f):
        owner,sv,owner_token=await setup(f); _,_,other_token=await setup(f)
        async with api_client(f) as c: created=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {owner_token}'},json={'server_id':str(sv.id),'public_key':key()})
        cid=created.json()['credential_id']
        async with api_client(f) as c: response=await c.delete(f'/api/v1/vpn/credentials/{cid}',headers={'Authorization':f'Bearer {other_token}'})
        assert response.status_code==404
        async with f() as s: assert (await s.get(VPNCredential,cid)).status is VPNCredentialStatus.ACTIVE
    run_database_test(scenario)

def test_revoke_is_idempotent():
    async def scenario(f):
        _,sv,t=await setup(f)
        async with api_client(f) as c:
            created=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()}); cid=created.json()['credential_id']
            assert (await c.delete(f'/api/v1/vpn/credentials/{cid}',headers={'Authorization':f'Bearer {t}'})).status_code==204
            assert (await c.delete(f'/api/v1/vpn/credentials/{cid}',headers={'Authorization':f'Bearer {t}'})).status_code==204
        async with f() as s: assert (await s.get(VPNCredential,cid)).status is VPNCredentialStatus.REVOKED
    run_database_test(scenario)

def test_server_private_key_is_not_persisted():
    assert 'private_key' not in Base.metadata.tables['vpn_servers'].columns
    assert 'private_key' not in Base.metadata.tables['vpn_credentials'].columns
    assert 'private_key' not in {c.name for t in Base.metadata.tables.values() for c in t.columns}

def test_revoke_reachable_node_clears_pending(monkeypatch):
    calls=[]
    async def remove(*args): calls.append(args)
    monkeypatch.setattr('app.services.vpn_provisioning.remove_peer',remove)
    async def scenario(f):
        _,sv,t=await setup(f)
        async with api_client(f) as c: created=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()}); cid=created.json()['credential_id']; assert (await c.delete(f'/api/v1/vpn/credentials/{cid}',headers={'Authorization':f'Bearer {t}'})).status_code==204
        async with f() as s: cred=await s.get(VPNCredential,cid); assert cred.status is VPNCredentialStatus.REVOKED and cred.node_sync_pending is False
        assert calls
    run_database_test(scenario)

def test_revoke_unavailable_node_sets_pending(monkeypatch):
    async def remove(*args): raise NodeUnavailableError
    monkeypatch.setattr('app.services.vpn_provisioning.remove_peer',remove)
    async def scenario(f):
        _,sv,t=await setup(f)
        async with api_client(f) as c: created=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()}); cid=created.json()['credential_id']; assert (await c.delete(f'/api/v1/vpn/credentials/{cid}',headers={'Authorization':f'Bearer {t}'})).status_code==204
        async with f() as s: cred=await s.get(VPNCredential,cid); assert cred.status is VPNCredentialStatus.REVOKED and cred.node_sync_pending is True
    run_database_test(scenario)

def test_successful_reconciliation_clears_pending(monkeypatch):
    async def remove(*args): return None
    monkeypatch.setattr('app.services.vpn_provisioning.remove_peer',remove)
    async def scenario(f):
        _,sv,t=await setup(f); admin,_,at=await setup(f,admin=True)
        async with api_client(f) as c: created=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()}); cid=created.json()['credential_id']; await c.delete(f'/api/v1/vpn/credentials/{cid}',headers={'Authorization':f'Bearer {t}'})
        async with f.begin() as s: cred=await s.get(VPNCredential,cid); cred.node_sync_pending=True
        async with api_client(f) as c: response=await c.post('/api/v1/admin/vpn/reconcile',headers={'Authorization':f'Bearer {at}'})
        assert response.status_code==200
        async with f() as s: assert (await s.get(VPNCredential,cid)).node_sync_pending is False
    run_database_test(scenario)

def test_failed_reconciliation_keeps_pending(monkeypatch):
    async def remove(*args): raise NodeUnavailableError
    monkeypatch.setattr('app.services.vpn_provisioning.remove_peer',remove)
    async def scenario(f):
        _,sv,t=await setup(f); _,_,at=await setup(f,admin=True)
        async with api_client(f) as c: created=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()}); cid=created.json()['credential_id']; await c.delete(f'/api/v1/vpn/credentials/{cid}',headers={'Authorization':f'Bearer {t}'})
        async with f.begin() as s: cred=await s.get(VPNCredential,cid); cred.node_sync_pending=True
        async with api_client(f) as c: response=await c.post('/api/v1/admin/vpn/reconcile',headers={'Authorization':f'Bearer {at}'})
        assert response.status_code==200
        async with f() as s: assert (await s.get(VPNCredential,cid)).node_sync_pending is True
    run_database_test(scenario)

def test_reconciliation_is_idempotent(monkeypatch):
    async def remove(*args): return None
    monkeypatch.setattr('app.services.vpn_provisioning.remove_peer',remove)
    async def scenario(f):
        _,sv,t=await setup(f); _,_,at=await setup(f,admin=True)
        async with api_client(f) as c: created=await c.post('/api/v1/vpn/provision',headers={'Authorization':f'Bearer {t}'},json={'server_id':str(sv.id),'public_key':key()}); cid=created.json()['credential_id']; await c.delete(f'/api/v1/vpn/credentials/{cid}',headers={'Authorization':f'Bearer {t}'})
        async with f.begin() as s: cred=await s.get(VPNCredential,cid); cred.node_sync_pending=True
        async with api_client(f) as c: first=await c.post('/api/v1/admin/vpn/reconcile',headers={'Authorization':f'Bearer {at}'}); second=await c.post('/api/v1/admin/vpn/reconcile',headers={'Authorization':f'Bearer {at}'})
        assert first.status_code==second.status_code==200 and second.json()['reconciled']==0
    run_database_test(scenario)
