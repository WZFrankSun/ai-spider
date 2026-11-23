import unittest

from app.monitoring.application.phrase_matching import (
    JsonPhraseSetLoader,
    match_add_to_cart,
    normalize_ocr_text,
)


class PhraseMatchingTests(unittest.TestCase):
    def test_matches_english_with_case_punctuation_and_hyphen_variants(self):
        result = match_add_to_cart(
            "ADD-to-cart",
            ["Add to cart", "Add to basket"],
        )

        self.assertTrue(result.matched)
        self.assertEqual(result.matched_phrase, "Add to cart")

    def test_matches_german_and_italian_diacritics(self):
        german = match_add_to_cart("In den Einkaufswagen", ["In den Warenkorb", "In den Einkaufswagen"])
        italian = match_add_to_cart("Aggiungi al carrello", ["Aggiungi al carrello"])

        self.assertTrue(german.matched)
        self.assertEqual(german.matched_phrase, "In den Einkaufswagen")
        self.assertTrue(italian.matched)

    def test_collapses_ocr_whitespace_and_accents(self):
        self.assertEqual(normalize_ocr_text("  Aggiungi\n  al   carrello  "), "aggiungi al carrello")
        result = match_add_to_cart("In den Warenkörb", ["In den Warenkorb"])
        self.assertTrue(result.matched)

    def test_returns_unmatched_result_without_phrase(self):
        result = match_add_to_cart("Only price and shipping", ["Add to cart"])

        self.assertFalse(result.matched)
        self.assertIsNone(result.matched_phrase)

    def test_loads_country_platform_phrase_set(self):
        loader = JsonPhraseSetLoader("config/phrase_sets.example.json")

        phrases = loader.load(country="DE", platform="amazon", page_type="product_detail")

        self.assertIn("In den Warenkorb", phrases)


if __name__ == "__main__":
    unittest.main()
