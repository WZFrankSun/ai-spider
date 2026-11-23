import unittest
from datetime import datetime, timezone

from app.monitoring.adapters.memory_repositories import MemoryAlertRepository
from app.monitoring.application.dismiss_alert import DismissAlert, DismissRequest
from app.monitoring.domain.models import Alert, AlertStatus, AlertType


def alert(status=AlertStatus.OPEN):
    return Alert("alert-1", AlertType.PRODUCT_ADD_TO_CART_MISSING, status, "DE-001")


class DismissAlertTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_can_be_dismissed_with_reason_and_transition(self):
        repo = MemoryAlertRepository(); await repo.save(alert())
        result = await DismissAlert(repo).execute("alert-1", DismissRequest("local-operator", "confirmed_false_positive", "OCR phrase missing"))
        self.assertEqual(result.status, AlertStatus.DISMISSED)
        self.assertEqual(result.metadata["resolved_by"], "local-operator")
        self.assertEqual(len(repo.transitions), 1)

    async def test_dismiss_is_idempotent(self):
        repo = MemoryAlertRepository(); await repo.save(alert())
        use_case = DismissAlert(repo); request = DismissRequest("local-operator", "confirmed_false_positive", "note")
        await use_case.execute("alert-1", request); await use_case.execute("alert-1", request)
        self.assertEqual(len(repo.transitions), 1)

    async def test_resolved_cannot_be_dismissed(self):
        repo = MemoryAlertRepository(); await repo.save(alert(AlertStatus.RESOLVED))
        with self.assertRaises(ValueError):
            await DismissAlert(repo).execute("alert-1", DismissRequest("local-operator", "confirmed_false_positive", "note"))


if __name__ == "__main__": unittest.main()
