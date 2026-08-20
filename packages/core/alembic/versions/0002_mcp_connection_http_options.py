"""Add per-connection HTTP options for MCP outbound calls."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_connections",
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "mcp_connections",
        sa.Column("trust_env", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("mcp_connections", "trust_env")
    op.drop_column("mcp_connections", "verify_ssl")
