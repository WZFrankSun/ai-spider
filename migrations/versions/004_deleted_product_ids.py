"""Remember deleted product IDs to prevent catalog reimport."""

from alembic import op
import sqlalchemy as sa

revision = "004_deleted_product_ids"
down_revision = "003_drop_product_postal_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deleted_product_ids",
        sa.Column("product_id", sa.String(120), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("deleted_product_ids")
