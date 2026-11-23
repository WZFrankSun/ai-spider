"""Create monitoring persistence tables.

Revision ID: 001_monitoring_tables
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "001_monitoring_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("sku", sa.String(160), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("page_type", sa.String(80), nullable=False),
        sa.Column("roi_profile_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(40), nullable=False, server_default="not_scanned"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("country", "platform", "sku", name="uq_products_market_sku"),
    )

    op.create_table(
        "scan_runs",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("product_id", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("matched_phrase", sa.String(255)),
        sa.Column("ocr_confidence", sa.Float()),
        sa.Column("error_code", sa.String(120)),
        sa.Column("error_message", sa.Text()),
        sa.Column("full_screenshot_path", sa.Text()),
        sa.Column("roi_screenshot_path", sa.Text()),
        sa.Column("cookie_summary", sa.JSON(), nullable=False),
    )
    op.create_index("ix_scan_runs_product_id", "scan_runs", ["product_id"])
    op.create_index("ix_scan_runs_product_started", "scan_runs", ["product_id", "started_at"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("product_id", sa.String(120), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("operator_note", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alerts_type", "alerts", ["type"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_product_id", "alerts", ["product_id"])

    op.create_table(
        "alert_transitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.String(160), nullable=False),
        sa.Column("from_status", sa.String(40)),
        sa.Column("to_status", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("operator", sa.String(120)),
        sa.Column("scan_id", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alert_transitions_alert_id", "alert_transitions", ["alert_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("product_id", sa.String(120), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("sku", sa.String(160), nullable=False),
        sa.Column("artifact_type", sa.String(40), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_artifacts_product_id", "artifacts", ["product_id"])

    op.create_table(
        "roi_profiles",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("page_type", sa.String(80), nullable=False),
        sa.Column("selector", sa.Text()),
        sa.Column("region", sa.JSON()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "phrase_sets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("page_type", sa.String(80), nullable=False),
        sa.Column("phrases", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_table("phrase_sets")
    op.drop_table("roi_profiles")
    op.drop_index("ix_artifacts_product_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_alert_transitions_alert_id", table_name="alert_transitions")
    op.drop_table("alert_transitions")
    op.drop_index("ix_alerts_product_id", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_index("ix_alerts_type", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_scan_runs_product_started", table_name="scan_runs")
    op.drop_index("ix_scan_runs_product_id", table_name="scan_runs")
    op.drop_table("scan_runs")
    op.drop_table("products")
