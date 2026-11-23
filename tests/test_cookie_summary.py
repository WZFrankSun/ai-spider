import unittest

from app.monitoring.application.cookie_summary import summarize_cookies


class CookieSummaryTests(unittest.TestCase):
    def test_summary_keeps_metadata_and_hash_without_raw_cookie_value(self):
        cookies = [
            {
                "name": "session",
                "value": "secret-cookie-value",
                "domain": ".example.com",
                "path": "/",
                "expires": 1893456000,
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]

        summaries = summarize_cookies(cookies)

        self.assertEqual(summaries[0]["name"], "session")
        self.assertTrue(summaries[0]["present"])
        self.assertNotIn("value", summaries[0])
        self.assertNotIn("secret-cookie-value", str(summaries))
        self.assertEqual(len(summaries[0]["value_hash"]), 64)

    def test_empty_or_missing_value_is_not_hashed_as_secret(self):
        summaries = summarize_cookies([{"name": "empty", "domain": "example.com"}])

        self.assertFalse(summaries[0]["present"])
        self.assertIsNone(summaries[0]["value_hash"])


if __name__ == "__main__":
    unittest.main()
