from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.admin_servers import router as admin_servers_router
from app.api.health import router as health_router
from app.api.node import router as node_router
from app.api.servers import router as servers_router
from app.api.users import router as users_router
from app.api.vpn import router as vpn_router
from app.api.admin_vpn import router as admin_vpn_router


def create_app() -> FastAPI:
    """Create the HTTP application without connecting to external services."""
    app = FastAPI(title="VPN MVP API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(servers_router)
    app.include_router(admin_servers_router)
    app.include_router(node_router)
    app.include_router(vpn_router)
    app.include_router(admin_vpn_router)
    return app


app = create_app()
