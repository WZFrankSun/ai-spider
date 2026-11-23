from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.monitoring.application.ports import AlertRepository
from app.monitoring.domain.models import AlertStatus


@dataclass(frozen=True)
class DismissRequest:
    operator: str
    reason: str
    note: str


class DismissAlert:
    def __init__(self, alerts: AlertRepository):
        self.alerts = alerts

    async def execute(self, alert_id: str, request: DismissRequest):
        alert = await self.alerts.get(alert_id)
        if alert is None:
            raise KeyError(f"unknown alert: {alert_id}")
        if alert.status == AlertStatus.DISMISSED:
            return alert
        if alert.status == AlertStatus.RESOLVED:
            raise ValueError("resolved alert cannot be dismissed")
        previous = alert.status.value
        alert.status = AlertStatus.DISMISSED
        alert.metadata.update({
            "resolution_reason": request.reason,
            "resolution_note": request.note,
            "resolved_by": request.operator,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        })
        await self.alerts.save(alert)
        await self.alerts.record_transition(
            alert,
            from_status=previous,
            reason=f"{request.reason}: {request.note}".strip(": "),
            operator=request.operator,
        )
        return alert
