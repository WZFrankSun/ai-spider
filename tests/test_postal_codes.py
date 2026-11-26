import unittest

from app.monitoring.config.postal_codes import normalize_postal, postal_matches, postal_values_equal


class PostalCodeTests(unittest.TestCase):
    def test_normalize_postal(self):
        cases = (
            (None, ""),
            ("", ""),
            (" \t\n\u3000", ""),
            ("\u3000sw1a\t1aa\n", "SW1A1AA"),
            ("00-001", "00001"),
            ("0\u200b0\u200c0\u200d0\u200e1\u200f\ufeff\u00ad", "00001"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(normalize_postal(value), expected)

    def test_postal_matches_complete_values_in_readback(self):
        cases = (
            ("SW1A 1AA", "Lieferung nach London SW1A1AA", True),
            ("SW1A 1AA", "Lieferung nach London SW1A 1AA", True),
            ("SW1A 1AA", "Lieferung nach London SW1A\u200c1AA", True),
            ("SW1A 1AA", "Lieferung nach London SW1A1AB", False),
            ("10115", "Lieferung nach 10115 Berlin", True),
            ("10115", "Lieferung nach 101150 Berlin", False),
            ("00-001", "Dostawa do 00-001 Warszawa", True),
            ("00-001", "Dostawa do 00001 Warszawa", True),
            ("111 22", "Leverans till 111 22", True),
            ("111 22", "Leverans till 11122", True),
            ("10115", "Berlin X10115", False),
            ("10115", "Berlin 10115X", False),
            ("SW1A1AA", "London sw1a\u30001aa", True),
            ("", "Berlin 10115", False),
            (None, "Berlin 10115", False),
            ("10115", None, False),
        )
        for target, readback, expected in cases:
            with self.subTest(target=target, readback=readback):
                self.assertEqual(postal_matches(readback, target), expected)

    def test_postal_values_equal(self):
        self.assertTrue(postal_values_equal("SW1A 1AA", "sw1a1aa\u200c"))
        self.assertTrue(postal_values_equal("00-001", "00001"))
        self.assertTrue(postal_values_equal(None, ""))
        self.assertFalse(postal_values_equal("00174", "0174"))
        self.assertFalse(postal_values_equal("10115", "101150"))
