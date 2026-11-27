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

    def test_spanish_unavailable_set_covers_wishlist_only_listing(self):
        # 西班牙站无货时只显示愿望单按钮，不写任何不可购买文案，
        # 因此愿望单文案必须算作不可购买证据。
        loader = JsonPhraseSetLoader("config/phrase_sets.json")

        phrases = loader.load(
            country="ES", platform="amazon", page_type="product_detail", unavailable=True
        )
        result = match_add_to_cart(
            "Ver todas las opciones de compra Anadir a la Lista de deseos", phrases
        )

        self.assertTrue(result.matched)

    def test_italian_unavailable_set_covers_short_unavailable_wording(self):
        # 意大利站页面写的是短形式 "Non disponibile."，
        # 词库原来只有带前缀或后缀的长形式。
        loader = JsonPhraseSetLoader("config/phrase_sets.json")

        phrases = loader.load(
            country="IT", platform="amazon", page_type="product_detail", unavailable=True
        )
        result = match_add_to_cart("Non disponibile.", phrases)

        self.assertTrue(result.matched)


if __name__ == "__main__":
    unittest.main()
