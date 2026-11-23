from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlertType(str, Enum):
    PRODUCT_ADD_TO_CART_MISSING = "PRODUCT_ADD_TO_CART_MISSING"
    MONITORING_TECHNICAL_FAILURE = "MONITORING_TECHNICAL_FAILURE"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    PENDING_VERIFICATION = "pending_verification"
    RESOLVED = "resolved"
    REOPENED = "reopened"


class DemoProduct(BaseModel):
    id: str
    country: str
    platform: str
    sku: str
    name: str
    url: str
    page_type: str = "product_detail"
    roi_profile: str
    enabled: bool = True
    demo_status: str = "healthy"


class ScanResult(BaseModel):
    scan_id: str
    product_id: str
    country: str
    platform: str
    sku: str
    started_at: datetime
    finished_at: datetime
    status: str
    ocr_text: str = ""
    matched_phrase: str | None = None
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    full_screenshot_path: str | None = None
    roi_screenshot_path: str | None = None
    error: str | None = None


class AlertEvent(BaseModel):
    id: str
    type: AlertType
    status: AlertStatus
    product_id: str
    country: str
    platform: str
    sku: str
    url: str
    first_seen_at: datetime
    last_seen_at: datetime
    failure_count: int = 1
    full_screenshot_path: str | None = None
    roi_screenshot_path: str | None = None
    ocr_text: str = ""
    matched_phrase: str | None = None
    operator_note: str | None = None
