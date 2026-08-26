"""Ensure one active credential per user/server/public key."""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
revision = "20260826_05"
down_revision: str | Sequence[str] | None = "20260826_04"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.create_index("uq_vpn_credentials_active_identity", "vpn_credentials", ["user_id", "server_id", "public_key"], unique=True, postgresql_where=sa.text("status = 'ACTIVE'"))
def downgrade() -> None:
    op.drop_index("uq_vpn_credentials_active_identity", table_name="vpn_credentials")
