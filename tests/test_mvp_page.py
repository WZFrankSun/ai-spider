import unittest

from fastapi.testclient import TestClient

from app.monitoring.api.routes import create_monitoring_app


class MvpPageTests(unittest.TestCase):
    def test_page_contains_state_controls_and_tables(self):
        client = TestClient(create_monitoring_app())

        response = client.get("/")
        html = response.text

        self.assertEqual(response.status_code, 200)
        for text in (
            "not_scanned",
            "scanning",
            "healthy",
            "inventory_risk",
            "technical_failure",
            "演示结果",
            "商品扫描",
            "告警事件",
            "标记已处理并验证",
            "错误原因",
            "data-product-id",
            'id="toast-region"',
            "aria-live",
            "data-operation",
            "data-last-scan",
            "data-scan-duration",
            "AbortController",
            "showToast",
            "NETWORK_ERROR_MESSAGE",
            "prefers-reduced-motion",
        ):
            self.assertIn(text, html)

    def test_page_contains_monitoring_status_panel(self):
        html = TestClient(create_monitoring_app()).get("/").text
        self.assertIn("monitoring-status", html)
        self.assertIn("扫描航线", html)

    def test_page_contains_ocr_evidence_and_screenshot_columns(self):
        html = TestClient(create_monitoring_app()).get("/").text
        self.assertIn("OCR 证据", html)
        self.assertIn("截图证据", html)


if __name__ == "__main__":
    unittest.main()
