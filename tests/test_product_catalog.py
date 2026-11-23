import json
import tempfile
import unittest
from pathlib import Path

from app.monitoring.adapters.product_catalog import (
    CatalogValidationError,
    JsonProductCatalogLoader,
)
from app.monitoring.domain.models import Product


class ProductCatalogTests(unittest.TestCase):
    def write_catalog(self, payload) -> str:
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with handle:
            json.dump(payload, handle)
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def product(self, **overrides) -> dict:
        record = {
            "id": "DE-amazon-SKU-001",
            "country": "DE",
            "platform": "amazon",
            "sku": "SKU-001",
            "name": "Bathroom tap",
            "url": "https://example.test/de/product-001",
            "page_type": "product_detail",
            "roi_profile": "amazon_product_detail_de",
            "enabled": True,
        }
        record.update(overrides)
        return record

    def test_loads_enabled_products_from_wrapped_json(self):
        path = self.write_catalog({"products": [self.product()]})

        products = JsonProductCatalogLoader().load(path)

        self.assertEqual(len(products), 1)
        self.assertIsInstance(products[0], Product)
        self.assertEqual(products[0].id, "DE-amazon-SKU-001")
        self.assertEqual(products[0].roi_profile_id, "amazon_product_detail_de")

    def test_filters_disabled_products(self):
        path = self.write_catalog([self.product(enabled=False)])

        products = JsonProductCatalogLoader().load(path)

        self.assertEqual(products, [])

    def test_rejects_invalid_country(self):
        path = self.write_catalog([self.product(country="ES")])

        with self.assertRaises(CatalogValidationError):
            JsonProductCatalogLoader().load(path)

    def test_rejects_duplicate_market_product(self):
        path = self.write_catalog([
            self.product(),
            self.product(id="DE-amazon-SKU-001-copy"),
        ])

        with self.assertRaises(CatalogValidationError):
            JsonProductCatalogLoader().load(path)


if __name__ == "__main__":
    unittest.main()
