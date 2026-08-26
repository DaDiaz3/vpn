"""Add WireGuard provisioning metadata and credential IP allocation."""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision = "20260826_03"
down_revision: str | Sequence[str] | None = "20260826_02"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("vpn_servers", sa.Column("network_cidr", sa.String(43), server_default="10.20.0.0/24", nullable=False))
    op.add_column("vpn_servers", sa.Column("endpoint", sa.String(255), server_default="", nullable=False))
    op.add_column("vpn_servers", sa.Column("wireguard_public_key", sa.String(64), server_default="", nullable=False))
    op.add_column("vpn_servers", sa.Column("dns", sa.String(255), server_default="1.1.1.1", nullable=False))
    op.add_column("vpn_credentials", sa.Column("assigned_ip", sa.String(43), nullable=True))
    op.create_index("uq_vpn_credentials_server_assigned_ip", "vpn_credentials", ["server_id", "assigned_ip"], unique=True, postgresql_where=sa.text("status = 'ACTIVE' AND assigned_ip IS NOT NULL"))

def downgrade() -> None:
    op.drop_index("uq_vpn_credentials_server_assigned_ip", table_name="vpn_credentials")
    op.drop_column("vpn_credentials", "assigned_ip")
    for column in ("dns", "wireguard_public_key", "endpoint", "network_cidr"):
        op.drop_column("vpn_servers", column)
