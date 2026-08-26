# Architecture

## Scope of this MVP

The initial commercial product has an iOS client, a Python backend, PostgreSQL, Redis, and four VPN server locations. It supports a seven-day trial followed by a USD 9.99 monthly subscription. These are product requirements, not implemented behavior in the current scaffold.

The first release must collect only operational metrics necessary to assess VPN quality and infrastructure health. It must not collect user traffic payloads, URLs, browsing history, or DNS query content.

## Component view

```text
iOS app ── HTTPS ──> FastAPI backend ──> PostgreSQL
   │                         │
   │                         └──────────> Redis
   │
   └── Network Extension ── encrypted VPN tunnel ──> VPN server fleet
                                                     │
                                                     └── health metrics ──> backend
```

The transport protocol and VPN server implementation are explicitly outside this stage.

## Planned boundaries

| Component | Responsibility | Excluded at this stage |
| --- | --- | --- |
| iOS app | UI, StoreKit 2 purchase state, Keychain-backed local secrets, connection intent | Tunnel implementation and subscription flows |
| Packet Tunnel extension | Isolated Network Extension target for future tunnel lifecycle | Packet handling, protocol configuration, credentials |
| API | Client API, internal server-health API, authorization boundary | User, billing, configuration, and selection logic |
| PostgreSQL | Durable user, subscription, server, credential, session, and aggregate-quality-metric state | VPN private keys, traffic payloads, URLs, and DNS history |
| Redis | Ephemeral cache, rate limiting, future health freshness | No keys or cache policies yet |
| VPN server fleet | One server per location at launch; emits aggregate health data | Traffic inspection or user-activity logging |

## Server choice and connection stability

Future server selection should occur only when a client requests a new connection configuration. The backend should select from healthy servers using location, capacity, latency/quality, and rollout constraints. Its selected server and configuration version should be persisted for that connection or session.

An active tunnel remains pinned to its assigned server. It is not rebalanced merely because another server becomes preferable. A migration should be considered only after an explicit reconnect, user action, configuration expiry, or a documented failure-recovery policy.

To scale from four to many servers, server records, health records, capacity signals, and configuration versions must be separate from the selection policy. Server instances need stable IDs and location metadata; the selector must use data-driven eligibility rather than a fixed list in application code.

## Data and privacy boundaries

Allowed future metrics are aggregate and technical: server CPU/memory/disk, tunnel process health, active connection count, capacity, packet loss aggregate, handshake/connect error counts, and coarse latency measurements. Metric retention and aggregation windows must be defined before implementation.

Prohibited data includes packet contents, site/URL history, DNS query contents, and user traffic logs. Logs must avoid credentials, tokens, IP addresses unless a later privacy review explicitly approves a narrowly scoped operational need, and any request/response body logging on VPN paths must remain disabled.

## Database foundation

The PostgreSQL foundation uses UUID primary keys, timezone-aware timestamps, explicit foreign keys, and native PostgreSQL enums. `users.password_hash` is reserved for a one-way password hash; passwords are never stored. The `subscriptions` table retains a provider and external transaction identifier for a future Apple StoreKit 2/App Store Server API integration, but does not implement purchase verification.

`vpn_credentials` stores only a public key and revocation state. User private keys and server private keys are prohibited from the database. `server_metrics` and `connection_metrics` contain only aggregate technical measurements such as resource utilisation, capacity signals, latency, throughput, and connection outcome; no user traffic content is modelled.

## Authentication boundary

The API provides a minimal email/password registration and login boundary for the iOS client. Passwords are validated at the request boundary and stored only as Argon2id hashes. Access tokens are signed JWTs with subject, issued-at, expiration, and token-type claims. The signing key is supplied only through `JWT_SECRET_KEY`; a server with no configured key cannot perform authentication.

Registration assigns an active seven-day trial using UTC timestamps. Trial state is computed separately from payment/subscription handling: active trial, expired trial, subscribed (reserved for a future provider), or access expired. A suspended or deleted user cannot receive or use an access token.

## Node registry and health monitoring

Administrators are explicit `users.is_admin` principals, not a list of privileged email addresses. A VPN node receives a separate high-entropy secret through an out-of-band deployment channel. The backend stores only its Argon2 hash in `node_credentials`, bound one-to-one to a `vpn_servers` record. Nodes submit the secret in `X-Node-Secret` over HTTPS; this credential is never returned by any API or written to logs. User JWTs cannot authenticate node endpoints.

Each accepted heartbeat stores one aggregate `server_metrics` row and updates `vpn_servers.last_seen_at` with backend UTC time. The `(server_id, timestamp, id)` index supports a correlated latest-row query for the registry, rather than loading all historical metrics or issuing one query per server.

Health thresholds are environment configuration, not magic values: default heartbeat interval is 30 seconds; a node is `OFFLINE` after 90 seconds without an accepted heartbeat. A recent heartbeat is `DEGRADED` when CPU or memory is at least 85%, packet loss at least 5%, latency at least 250 ms, or active users are at least 90% of declared capacity; otherwise it is `ONLINE`. `MAINTENANCE` is an administrator-controlled state and is not overwritten by heartbeats. The backend rejects timestamps outside the configured 300-second skew window and invalid metric ranges.

## Delivery phases after this scaffold

## Stage 5 provisioning boundary

The control plane exposes authenticated `/api/v1/vpn/provision` and credential revoke endpoints. It stores only the user public key and an assigned client address; private keys are generated and retained by the iOS client. A VPN server's WireGuard public metadata and client network are stored in `vpn_servers`; server private keys remain on the node. The control plane calls the node provisioning agent over TLS using a separately configured service token. The agent accepts only validated add/remove peer operations and invokes fixed `wg set` commands (never generic shell input). IP allocation reserves the node address and uses a transaction advisory lock plus a partial unique index for active credentials; revoked addresses may be reused.

1. Approve data model, API contracts, privacy/retention policy, and StoreKit entitlement-verification design.
2. Add database configuration, SQLAlchemy models, Alembic baseline, and internal server-health ingestion.
3. Add iOS account/purchase state, Keychain wrapper, and configuration retrieval.
4. Design and implement the VPN protocol and Packet Tunnel lifecycle following a dedicated security review.
