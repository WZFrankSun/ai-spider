import unittest
from pathlib import Path

from app.monitoring.adapters.roi import JsonRoiProfileLoader
from app.monitoring.api.schemas import ProductEntryRequest
from app.monitoring.application.phrase_matching import JsonPhraseSetLoader
from app.monitoring.config.markets import DEFAULT_POSTAL_CODES, ENTRY_COUNTRIES, LIVE_AMAZON_COUNTRIES


class AmazonMarketTests(unittest.TestCase):
    def test_nine_markets_have_entry_live_roi_and_phrases(self):
        domains = dict(DE="de", IT="it", FR="fr", ES="es", GB="co.uk",
                       SE="se", BE="com.be", PL="pl", NL="nl")
        self.assertEqual(set(domains), set(ENTRY_COUNTRIES))
        self.assertEqual(set(domains), LIVE_AMAZON_COUNTRIES)
        root = Path(__file__).resolve().parents[1]
        roi = JsonRoiProfileLoader(root / "config/roi_profiles.json")
        phrases = JsonPhraseSetLoader(root / "config/phrase_sets.json")
        for market, suffix in domains.items():
            with self.subTest(market=market):
                data = dict(platform="amazon", store_code="H1-A1", country=market,
                            sku="test", name="test", added_by="Frank",
                            url=f"https://www.amazon.{suffix}/dp/B07Q3DYMRD")
                self.assertEqual(ProductEntryRequest(**data).country, market)
                with self.assertRaises(ValueError):
                    ProductEntryRequest(**data, postal_code="99999")
                self.assertTrue(DEFAULT_POSTAL_CODES[market])
                self.assertEqual(roi.load(f"amazon_product_detail_{market.lower()}_buy_box").selector, "#rightCol")
                self.assertTrue(phrases.load(market, "amazon", "product_detail"))
                self.assertTrue(phrases.load(market, "amazon", "product_detail", unavailable=True))
