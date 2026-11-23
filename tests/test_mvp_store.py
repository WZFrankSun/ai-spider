import unittest

from app.mvp.store import DemoStore


class DemoStoreTests(unittest.TestCase):
    def test_contains_germany_and_italy_products(self):
        store = DemoStore()

        products = store.list_products()

        self.assertEqual(len(products), 20)
        self.assertEqual({product.country for product in products}, {"DE", "IT"})


    def test_missing_add_to_cart_creates_one_open_alert_and_repeat_updates_it(self):
        store = DemoStore()

        first = store.scan_product("DE-001")
        second = store.scan_product("DE-001")

        self.assertEqual(first.status, "inventory_risk")
        self.assertEqual(second.status, "inventory_risk")
        alerts = store.list_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].failure_count, 2)


    def test_verification_resolves_alert_after_simulated_recovery(self):
        store = DemoStore()
        store.scan_product("DE-001")

        event = store.verify_alert("alert-DE-001")

        self.assertEqual(event.status, "resolved")
        self.assertEqual(event.type, "PRODUCT_ADD_TO_CART_MISSING")


    def test_unknown_product_is_rejected(self):
        store = DemoStore()

        with self.assertRaisesRegex(KeyError, "unknown product: unknown"):
            store.scan_product("unknown")
