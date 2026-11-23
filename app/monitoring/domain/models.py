from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ProductScanStatus(str, Enum):
    NOT_SCANNED = "not_scanned"
    SCANNING = "scanning"
    HEALTHY = "healthy"
    INVENTORY_RISK = "inventory_risk"
    TECHNICAL_FAILURE = "technical_failure"


class AlertType(str, Enum):
    PRODUCT_ADD_TO_CART_MISSING = "PRODUCT_ADD_TO_CART_MISSING"
    MONITORING_TECHNICAL_FAILURE = "MONITORING_TECHNICAL_FAILURE"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    PENDING_VERIFICATION = "pending_verification"
    RESOLVED = "resolved"
    REOPENED = "reopened"
    DISMISSED = "dismissed"


@dataclass
class Product:
    id: str
    country: str
    platform: str
    sku: str
    url: str
    page_type: str
    roi_profile_id: str
    name: str = ""
    enabled: bool = True
    status: ProductScanStatus = ProductScanStatus.NOT_SCANNED
    delivery_validation_required: bool = True


@dataclass
class ScanObservation:
    status: ProductScanStatus
    ocr_text: str = ""
    matched_phrase: str | None = None
    confidence: float | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    full_screenshot_path: str | None = None
    roi_screenshot_path: str | None = None
    cookie_summary: list[dict] = field(default_factory=list)


@dataclass
class Scan:
    id: str
    product_id: str
    status: ProductScanStatus
    observation: ScanObservation
    started_at: datetime
    finished_at: datetime


@dataclass
class Alert:
    id: str
    type: AlertType
    status: AlertStatus
    product_id: str
    failure_count: int = 1
    operator_note: str | None = None
    metadata: dict = field(default_factory=dict)

    def apply_observation(self, observation: ScanObservation) -> "Alert":
        from .policies import can_resolve_alert

        if can_resolve_alert(self, observation):
            self.status = AlertStatus.RESOLVED
        elif observation.status == ProductScanStatus.INVENTORY_RISK:
            self.status = AlertStatus.REOPENED
            self.failure_count += 1
        elif observation.status == ProductScanStatus.TECHNICAL_FAILURE:
            self.status = AlertStatus.PENDING_VERIFICATION
        return self
