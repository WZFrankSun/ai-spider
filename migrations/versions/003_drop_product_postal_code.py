"""Remove the retired product postal code column."""

from alembic import op
import sqlalchemy as sa

revision = "003_drop_product_postal_code"
down_revision = "002_product_entry_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("products", "postal_code")


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column("postal_code", sa.String(24), nullable=False, server_default=""),
    )
