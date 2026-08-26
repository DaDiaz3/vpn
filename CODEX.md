# Project rules

## Scope and safety

- Build an iOS VPN product; do not add Android, web clients, or desktop clients unless explicitly requested.
- Do not inspect, store, log, or transmit user traffic content, URLs, DNS queries, browsing history, or payloads.
- Collect only documented, aggregate technical metrics needed for VPN quality and infrastructure health.
- Do not implement a VPN transport/protocol, encryption design, packet handling, or server provisioning unless the task explicitly requests it.
- Do not add authentication, billing, trial, server-selection, or migration business logic until their requirements are approved.

## Backend

- Target Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis, and pytest.
- Keep API routes thin; put future domain rules in explicit application/domain layers.
- Use async database drivers and migrations for persistent schema changes.
- Add tests for every behavior change. Never require live production infrastructure for unit tests.
- Health endpoints must not expose secrets, tokens, customer data, or internal topology.

## iOS

- Use Swift, SwiftUI, StoreKit 2, Keychain, and Network Extension only through supported Apple APIs.
- Keep UI, app state, purchase handling, credentials, and tunnel-extension code in separate modules/targets.
- Never put VPN credentials, shared secrets, or production endpoints in source control.

## Repository hygiene

- Keep documentation in `docs/` aligned with architectural decisions.
- Do not commit `.env`, signing certificates, provisioning profiles, Xcode user data, build artifacts, or local database data.
- Prefer clear names, small cohesive modules, typed interfaces, and minimal dependencies.
