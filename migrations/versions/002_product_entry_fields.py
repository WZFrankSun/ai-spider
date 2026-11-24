"""Add store-level product entry fields."""
from alembic import op
import sqlalchemy as sa

revision = "002_product_entry_fields"
down_revision = "001_monitoring_tables"
branch_labels = None
depends_on = None

FIELDS = (("store_code", 32), ("asin", 10), ("added_by", 32), ("postal_code", 24))


def upgrade() -> None:
    for name, length in FIELDS:
        op.add_column("products", sa.Column(name, sa.String(length), nullable=False, server_default=""))
    op.create_unique_constraint(
        "uq_products_store_market_sku", "products", ["country", "platform", "store_code", "sku"]
    )
    op.drop_constraint("uq_products_market_sku", "products", type_="unique")


def downgrade() -> None:
    duplicate = op.get_bind().execute(sa.text(
        "SELECT 1 FROM products GROUP BY country, platform, sku HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError("Cross-store SKU duplicates prevent downgrade")
    op.create_unique_constraint("uq_products_market_sku", "products", ["country", "platform", "sku"])
    op.drop_constraint("uq_products_store_market_sku", "products", type_="unique")
    for name, _ in reversed(FIELDS):
        op.drop_column("products", name)
