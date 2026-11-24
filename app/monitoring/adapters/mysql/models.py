from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("country", "platform", "store_code", "sku", name="uq_products_store_market_sku"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    platform: Mapped[str] = mapped_column(String(80), nullable=False)
    sku: Mapped[str] = mapped_column(String(160), nullable=False)
    store_code: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    asin: Mapped[str] = mapped_column(String(10), nullable=False, server_default="")
    added_by: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    postal_code: Mapped[str] = mapped_column(String(24), nullable=False, server_default="")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[str] = mapped_column(String(80), nullable=False)
    roi_profile_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="not_scanned", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScanRunModel(Base):
    __tablename__ = "scan_runs"
    __table_args__ = (
        Index("ix_scan_runs_product_started", "product_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ocr_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    matched_phrase: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    roi_screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookie_summary: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class AlertModel(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    failure_count: Mapped[int] = mapped_column(default=1, nullable=False)
    operator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AlertTransitionModel(Base):
    __tablename__ = "alert_transitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scan_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    platform: Mapped[str] = mapped_column(String(80), nullable=False)
    sku: Mapped[str] = mapped_column(String(160), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RoiProfileModel(Base):
    __tablename__ = "roi_profiles"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    platform: Mapped[str] = mapped_column(String(80), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    page_type: Mapped[str] = mapped_column(String(80), nullable=False)
    selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PhraseSetModel(Base):
    __tablename__ = "phrase_sets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    platform: Mapped[str] = mapped_column(String(80), nullable=False)
    page_type: Mapped[str] = mapped_column(String(80), nullable=False)
    phrases: Mapped[list] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
