# Health Agent

The agent sends only node technical metrics to the control plane. It does not read packet payloads, URLs, DNS history, or VPN private keys.

```bash
cd infrastructure/health-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export CONTROL_PLANE_URL=https://api.example.com
export NODE_SERVER_ID=<server UUID>
export NODE_SECRET=<provisioned node secret>
export ACTIVE_USERS=0
python agent.py
```

`ACTIVE_USERS`, `HEALTH_AGENT_LATENCY_MS`, and `HEALTH_AGENT_PACKET_LOSS_PERCENT` are configured values in this stage; integration with a VPN process is explicitly out of scope. For local development only, use `ALLOW_INSECURE_HTTP=true` with an HTTP control-plane URL. Do not put `NODE_SECRET` in shell history, source control, or logs.
