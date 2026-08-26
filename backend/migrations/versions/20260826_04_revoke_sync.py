"""Track pending node peer synchronization."""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
revision = "20260826_04"
down_revision: str | Sequence[str] | None = "20260826_03"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.add_column("vpn_credentials", sa.Column("node_sync_pending", sa.Boolean(), server_default=sa.text("false"), nullable=False))
def downgrade() -> None:
    op.drop_column("vpn_credentials", "node_sync_pending")
