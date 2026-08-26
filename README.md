# VPN MVP

Monorepo for a commercial iOS VPN MVP. This initial scaffold intentionally contains no subscription logic, user management, server selection, telemetry collection, or VPN protocol implementation.

## Repository layout

- `backend/` — FastAPI service skeleton and its Python tooling.
- `ios/` — SwiftUI and Network Extension target source layout.
- `docs/` — architecture and product-boundary documentation.

## Prerequisites

- Python 3.13
- Docker Compose
- Xcode (for the iOS target; a macOS host is required)

## Run the backend locally

```bash
cp .env.example .env
docker compose up -d
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/health`. Interactive OpenAPI docs are at `http://127.0.0.1:8000/docs`.

Before using `/api/v1/auth/*`, set a strong unique `JWT_SECRET_KEY` in `.env` (for example, generate one with `openssl rand -hex 32`). Do not commit `.env`.

## Apply database migrations

With PostgreSQL running and `DATABASE_URL` set (the value in `.env.example` is suitable for local Docker Compose):

```bash
cd backend
source .venv/bin/activate
set -a; source ../.env; set +a
alembic upgrade head
```

To revert the initial schema during local development:

```bash
alembic downgrade base
```

## Run tests

```bash
cd backend
source .venv/bin/activate
pytest
```

The database model tests use a randomly named temporary schema in the local PostgreSQL instance. They read `TEST_DATABASE_URL`, falling back to the local Docker Compose database URL.

## Local services

```bash
docker compose ps
docker compose down
```

`docker compose down -v` also removes local database and Redis volumes; do not use it if their local data is needed.

## iOS scaffold

The Swift sources are organized by app and packet-tunnel-extension targets in `ios/VpnMvp/`. Before building, create/open an Xcode project with:

- an iOS App target named `VpnMvp` using SwiftUI;
- a Packet Tunnel Provider extension target named `VpnMvpTunnel`;
- the `NetworkExtension` capability on the extension target.

Copy the target source groups from this repository into the corresponding targets. Entitlements and provisioning profiles require an Apple Developer account and have deliberately not been committed as signed credentials.
