# VPN node provisioning agent

Run behind TLS (reverse proxy or mTLS) with `VPN_NODE_AGENT_TOKEN` set out-of-band. It accepts only authenticated add/remove peer requests and invokes the fixed `wg set wg0` command with validated WireGuard keys/IPs; it never accepts shell commands or logs secrets.
