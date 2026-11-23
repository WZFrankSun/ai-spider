# 真实扫描链路打通 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏当前 MVP Demo 模式的前提下，优先接入现有爬虫已经产出的截图数据，完成“截图文件/清单 → ROI → 本地 OCR → 加购词匹配 → 商品状态 → 告警/复查”的可运行链路；再保留 Playwright 实时截图作为后续可替换输入，并完成每小时调度、MySQL 持久化和证据清理的接入准备。

**Architecture:** 继续采用模块化单体。启动层根据配置组装商品目录、截图输入源、OCR、证据存储、仓储和调度器；应用层只依赖 `Scanner`、`OcrEngine`、仓储和证据端口；领域层保持现有状态机和告警边界。第一阶段使用爬虫导出的截图清单作为 `ScreenshotSource`，不重复访问商品页面；第二阶段再通过同一个 `Scanner` 接口切换到 Playwright 实时截图。Real 模式与 Demo 模式共用 `ScanProduct`、`VerifyAlert` 和 API 合同，差异只存在于启动组装和适配器实现。

**Tech Stack:** Python 3.12+、uv、FastAPI、Playwright、Pillow、Tesseract/pytesseract、SQLAlchemy 2.x、Alembic、MySQL 8.x、unittest。

**Spec:** `SPEC.md`、`docs/ARCHITECTURE.md`、`docs/production-readiness.md`、`Tasks.md`

## Global Constraints

- MVP 默认仍使用内存商品、`DemoScanner` 和 Demo 页面，不依赖真实商品页面、MySQL、Tesseract、Kafka 或飞书。
- 面向爬虫数据的第一条 Real 输入链路读取现有截图文件及其 JSON 清单，不要求本次重复执行爬虫或模拟德国本地网络环境。
- 截图清单必须能把商品 `id`/`sku`、国家、平台、截图路径和采集时间关联起来；缺少关联或文件不可读时只能产生 `technical_failure`。
- Real 输入模式默认是 `manifest`（爬虫截图清单）；`live`（Playwright 实时截图）作为后续开关，不能在未明确配置时替换截图清单。
- 真实扫描默认覆盖 DE/IT 合计 20 个商品，每小时一次，起步并发不超过 3 个浏览器任务。
- 页面可访问不等于识别到加购入口；只有 OCR 匹配加购词才是 `healthy`。
- `technical_failure` 不得转换为 `inventory_risk`，也不得自动关闭库存风险告警。
- OCR 只处理 ROI；完整 Cookie 值不得进入日志、图片元数据、告警或数据库。
- 所有 Python 依赖使用 uv 和锁文件管理；不引入 Kafka、Celery、微服务或分布式队列。
- 不自动修改电商平台库存，不自动点击真实加购或下单。
- 真实站点只使用明确授权的商品进行手动验收，自动化单测不得依赖外部网站。
- 当前工作区不是 Git 仓库，计划中的提交步骤改为变更记录和验证记录，不执行 commit/push。

## Review Focus

- **Real 模式配置缺项**：缺少商品清单、ROI、词库、Tesseract 或数据库配置时，应给出明确错误并保持 Demo 可启动；由 Task 1、Task 3 覆盖。
- **OCR 结果边界**：OCR 未匹配必须是 `inventory_risk`，OCR 超时/二进制缺失必须是 `technical_failure`；由 Task 2 覆盖。
- **Cookie 脱敏**：Cookie 摘要只能包含名称、域名、路径、过期时间、存在性和哈希；由 Task 2 覆盖。
- **启动与调度生命周期**：Real 模式只能启动一个调度任务，关闭服务时必须取消任务和浏览器；由 Task 5 覆盖。
- **证据与告警一致性**：图片清理不能删除告警结构化记录，技术故障不能关闭库存告警；由 Task 4、Task 5 覆盖。

---

## 文件边界总览

### 新增文件

- `app/monitoring/runtime_config.py`：Real/Demo 运行配置和路径解析。
- `app/monitoring/adapters/crawler_screenshot.py`：读取爬虫截图清单、校验商品映射并提供统一 `Scanner` 输入。
- `app/monitoring/application/real_observation.py`：OCR、词库和领域状态之间的结果组装。
- `app/monitoring/bootstrap.py`：根据运行配置组装容器、扫描器、仓储和调度器。
- `app/monitoring/adapters/mysql/health.py`：数据库连接和迁移前健康检查。
- `app/monitoring/adapters/mysql/artifact_repository.py`：Artifact 结构化索引仓储。
- `app/monitoring/entrypoints/service.py`：FastAPI lifespan 中的浏览器和调度生命周期。
- `docs/real-scan-runbook.md`：真实站点小规模验收和扩容手册。
- `config/products.real.example.json`：不含敏感信息的 Real 商品清单示例。
- `config/screenshots.manifest.example.json`：爬虫截图到商品、国家、平台和采集时间的映射示例。
- `tests/test_runtime_config.py`、`tests/test_crawler_screenshot_source.py`、`tests/test_real_observation.py`、`tests/test_real_bootstrap.py`、`tests/test_real_service_lifecycle.py`、`tests/test_artifact_repository.py`、`tests/integration/test_real_rollout_gates.py`。

### 修改文件

- `app/config.py`：增加运行模式、商品目录、ROI、词库、证据目录、数据库和调度配置。
- `app/config.py`：增加截图清单路径和 `manifest/live` 输入模式配置。
- `app/monitoring/domain/models.py`：补充 Cookie 摘要和必要的证据索引字段，保持向后兼容默认值。
- `app/monitoring/application/ports.py`：补充数据库健康、Artifact 查询和 OCR 结果端口。
- `app/monitoring/adapters/playwright_scanner.py`：注入 Cookie 摘要、保留 OCR 错误码、关联 Artifact 引用。
- `app/monitoring/adapters/mysql/models.py`、`repositories.py`：补充 Artifact 索引和必要的状态字段。
- `migrations/versions/001_monitoring_tables.py`：补充迁移字段或索引，保持可重复执行。
- `app/monitoring/api/routes.py`：使用启动层注入的 Real/Demo 容器，健康接口返回运行模式和调度状态。
- `app.py`：通过启动层创建应用，不在模块导入时访问真实站点或数据库。
- `app/mvp/templates/index.html`：Real 模式隐藏 Demo 结果控件，展示证据引用和错误原因。
- `.env.example`：补充非敏感配置项和示例连接串格式。
- `Tasks.md`、`docs/production-readiness.md`、`docs/ARCHITECTURE.md`：记录实现状态和未决人工验收项。

---

### Task 1: 运行配置和外部依赖预检

**Files:**

- Create: `app/monitoring/runtime_config.py`
- Modify: `app/config.py`
- Modify: `.env.example`
- Test: `tests/test_runtime_config.py`

**Interfaces:**

- Produces `RuntimeMode = Literal["demo", "real"]`。
- Produces `MonitoringRuntimeConfig` with fields `mode`, `input_mode`, `catalog_path`, `screenshot_manifest_path`, `screenshot_root`, `roi_profiles_path`, `phrase_sets_path`, `artifact_root`, `database_url`, `scheduler_enabled`, `scan_interval_seconds`, `max_concurrency`, `scan_timeout_seconds`, `tesseract_cmd`, `tesseract_languages`。
- Produces `load_monitoring_config(environ: Mapping[str, str] | None = None) -> MonitoringRuntimeConfig`。
- Produces `validate_real_prerequisites(config: MonitoringRuntimeConfig) -> list[str]`；Demo 模式返回空列表，不访问外部服务。

- [ ] **Step 1: Write the failing test**

  - `test_demo_mode_does_not_require_real_paths_or_database`
  - `test_real_mode_requires_catalog_roi_phrase_and_database_configuration`
  - `test_default_interval_is_3600_and_concurrency_is_3`
  - `test_path_values_are_resolved_relative_to_project_root`

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_runtime_config -v`

  Expected: FAIL because the runtime config module and loader do not exist.

- [ ] **Step 3: Implement the minimal configuration layer**

  - Extend `app/config.py` only with settings parsing; do not make `OPENAI_API_KEY` a Real 扫描前置条件。
  - Use `mode=demo` as the default.
  - Validate `scan_interval_seconds=3600`, `max_concurrency=3` and positive timeout values.
  - Do not log the database password or full connection string.
  - Add a preflight function that checks Tesseract executable and language data only when Real mode is selected.

- [ ] **Step 4: Run test to verify it passes**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_runtime_config -v`

  Expected: PASS; Demo mode remains loadable without Tesseract or MySQL.

- [ ] **Step 5: Record the dependency result**

  Record the installed Tesseract path/version and language data in `docs/production-readiness.md`; if unavailable, leave Real mode disabled and record the exact missing prerequisite.

---

### Task 2: 爬虫截图输入、OCR 结果组装、Cookie 摘要和错误码传递

**Files:**

- Create: `app/monitoring/adapters/crawler_screenshot.py`
- Create: `app/monitoring/application/real_observation.py`
- Modify: `app/monitoring/domain/models.py`
- Modify: `app/monitoring/application/ports.py`
- Modify: `app/monitoring/adapters/playwright_scanner.py`
- Test: `tests/test_real_observation.py`
- Test: `tests/test_crawler_screenshot_source.py`
- Modify: `tests/test_playwright_scanner.py`

**Interfaces:**

- `class CrawlerScreenshotRecord` fields: `product_id`, `path`, `captured_at`, optional `url`, `country`, `platform`, `sku`。
- `class ScreenshotSource`：按 `product_id` 返回截图字节和来源元数据；不得把原始 Cookie 写入元数据。
- `class JsonScreenshotManifestSource`：从现有爬虫导出的 JSON 清单读取截图，校验路径位于允许的截图根目录内。
- `class CrawlerScreenshotScanner`：实现现有 `Scanner.scan(product)`，从 `ScreenshotSource` 读取截图，按 ROI 配置裁剪，然后调用观察结果工厂；缺图、路径越界、清单映射冲突均为 `technical_failure`。
- `class RealObservationFactory` constructor consumes `OcrEngine` and `JsonPhraseSetLoader`.
- `async def RealObservationFactory.__call__(self, product: Product, page: object, roi_bytes: bytes) -> ScanObservation`。
- `ScanObservation.cookie_summary: list[dict]` defaults to `[]`。
- `ScanObservation.full_screenshot_path` and `roi_screenshot_path` remain optional strings.

- [ ] **Step 1: Write the failing test**

  - `test_manifest_source_loads_screenshot_for_product`
  - `test_manifest_source_rejects_path_outside_root`
  - `test_crawler_screenshot_scanner_maps_missing_file_to_technical_failure`
  - `test_crawler_screenshot_scanner_passes_roi_bytes_to_ocr`
  - `test_ocr_match_returns_healthy_and_phrase`
  - `test_ocr_without_phrase_returns_inventory_risk`
  - `test_ocr_timeout_returns_technical_failure`
  - `test_cookie_summary_never_contains_raw_value`
  - `test_playwright_scanner_preserves_ocr_error_code`

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_crawler_screenshot_source tests.test_real_observation tests.test_playwright_scanner -v`

  Expected: FAIL because the crawler screenshot source/scanner, result factory and observation fields are not wired.

- [ ] **Step 3: Implement the minimal result pipeline**

  - Read existing crawler screenshot bytes before considering live Playwright capture; this is the first real integration path。
  - Convert `OcrResult` to `ScanObservation`: matched phrase means `healthy`; valid OCR with no phrase means `inventory_risk`.
  - Catch `OcrError` and preserve its code (`TESSERACT_NOT_FOUND`, `OCR_TIMEOUT`, `OCR_FAILED`) as `technical_failure`.
  - Obtain cookies from the Playwright context only after page setup and pass them through `summarize_cookies`.
  - Never pass the raw Cookie value to `ScanObservation`, Artifact metadata, logs or API responses.

- [ ] **Step 4: Run test to verify it passes**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_crawler_screenshot_source tests.test_real_observation tests.test_playwright_scanner -v`

  Expected: PASS; crawler screenshot ingestion, ROI OCR and Cookie failure boundaries are explicit.

---

### Task 3: Real 容器组装和启动模式切换

**Files:**

- Create: `app/monitoring/bootstrap.py`
- Modify: `app/monitoring/api/routes.py`
- Modify: `app.py`
- Modify: `app/mvp/templates/index.html`
- Create: `config/products.real.example.json`
- Create: `config/screenshots.manifest.example.json`
- Test: `tests/test_real_bootstrap.py`
- Test: `tests/test_real_scan_api.py`

**Interfaces:**

- `def build_monitoring_container(config: MonitoringRuntimeConfig) -> MonitoringContainer`。
- `def create_application(config: MonitoringRuntimeConfig | None = None) -> FastAPI`。
- Real/manifest 组装必须连接 `JsonProductCatalogLoader`、`JsonRoiProfileLoader`、`JsonPhraseSetLoader`、`JsonScreenshotManifestSource`、`CrawlerScreenshotScanner`、`LocalArtifactStore`、`RealObservationFactory` 和 `ScanProduct`。
- Real/live 组装才连接 `PlaywrightScanner`；切换输入源不改变 `ScanProduct`、告警或 API 契约。
- Demo 组装继续返回 `MonitoringContainer.demo()`，不读取真实目录、不创建浏览器、不连接 MySQL。

- [ ] **Step 1: Write the failing test**

  - `test_demo_bootstrap_does_not_create_real_dependencies`
  - `test_real_bootstrap_loads_catalog_and_injects_real_scanner`
  - `test_manifest_mode_does_not_create_browser`
  - `test_real_health_reports_mode_and_prerequisite_state`
  - `test_real_mode_hides_demo_result_endpoint`

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_real_bootstrap tests.test_real_scan_api -v`

  Expected: FAIL because `app.py` currently always creates Demo 容器。

- [ ] **Step 3: Implement the bootstrap boundary**

  - Select mode from `MONITORING_MODE`, defaulting to `demo`.
  - In Real/manifest mode, fail before serving traffic when the catalog, screenshot manifest, ROI, phrase set or Tesseract preflight is missing; error text must identify the missing setting without printing secrets。
  - Keep `MonitoringContainer.from_dependencies` generic enough for MySQL repositories and memory test doubles.
  - Real mode must not expose `/api/products/{product_id}/demo-result`.
  - Do not run a real scan during module import or application construction.

- [ ] **Step 4: Run test to verify it passes**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_real_bootstrap tests.test_real_scan_api -v`

  Expected: PASS for Demo and manifest modes using fake dependencies and local fixture files；manifest 模式不创建浏览器。

---

### Task 4: MySQL 运行时接入和 Artifact 结构化索引

**Files:**

- Create: `app/monitoring/adapters/mysql/health.py`
- Create: `app/monitoring/adapters/mysql/artifact_repository.py`
- Modify: `app/monitoring/application/ports.py`
- Modify: `app/monitoring/adapters/mysql/models.py`
- Modify: `app/monitoring/adapters/mysql/repositories.py`
- Modify: `migrations/versions/001_monitoring_tables.py`
- Modify: `tests/integration/test_mysql_repositories.py`
- Test: `tests/test_artifact_repository.py`

**Interfaces:**

- `async def check_database(engine: AsyncEngine) -> DatabaseHealth`。
- `class ArtifactRepository(Protocol): async def add(...); async def list_for_product(...); async def mark_deleted(...)`。
- `class SqlAlchemyArtifactRepository` implements the Artifact repository without exposing `AsyncSession` to application code.
- Artifact records contain `product_id`, market identity, `artifact_type`, path, created time and deleted time; no Cookie value.

- [ ] **Step 1: Write the failing test**

  - `test_database_health_returns_ok_for_sqlite_contract_engine`
  - `test_artifact_index_can_be_saved_and_marked_deleted`
  - `test_real_database_url_is_never_echoed_in_health_error`
  - `test_mysql_repository_contract_still_passes_with_sqlite`

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_artifact_repository tests.integration.test_mysql_repositories -v`

  Expected: FAIL because the health and Artifact repository ports are not implemented.

- [ ] **Step 3: Implement the runtime persistence boundary**

  - Add Artifact model/repository and migration indexes.
  - Use `SELECT 1` for health checks and redact credentials from errors.
  - Keep SQLite contract tests separate from optional real MySQL integration; real MySQL tests run only when `MYSQL_TEST_URL` is explicitly set.
  - Use the existing local MySQL service only through an explicit connection string; do not infer credentials from the environment.

- [ ] **Step 4: Run test to verify it passes**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_artifact_repository tests.integration.test_mysql_repositories -v`

  Expected: PASS without requiring MySQL credentials; optional MySQL integration is reported separately.

---

### Task 5: FastAPI 生命周期、浏览器关闭和每小时调度

**Files:**

- Create: `app/monitoring/entrypoints/service.py`
- Modify: `app/monitoring/entrypoints/hourly_scan.py`
- Modify: `app/monitoring/api/routes.py`
- Modify: `app.py`
- Modify: `app/config.py`
- Test: `tests/test_real_service_lifecycle.py`
- Modify: `tests/test_scheduled_scan.py`

**Interfaces:**

- `@asynccontextmanager async def monitoring_lifespan(app: FastAPI, container: MonitoringContainer, config: MonitoringRuntimeConfig)`。
- `async def start_monitoring_runtime(...) -> RuntimeHandles`。
- `async def stop_monitoring_runtime(handles: RuntimeHandles) -> None`。
- `HourlyScanRunner.run_once()` remains the only business scan entrypoint; scheduler only triggers it.

- [ ] **Step 1: Write the failing test**

  - `test_real_lifespan_starts_scheduler_once`
  - `test_demo_lifespan_does_not_start_scheduler_or_browser`
  - `test_shutdown_cancels_scheduler_and_closes_browser`
  - `test_health_exposes_scheduler_state_without_credentials`

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_real_service_lifecycle -v`

  Expected: FAIL because the current app has no monitoring lifespan or scheduler task.

- [ ] **Step 3: Implement lifecycle wiring**

  - Start the BrowserManager once for Real mode and reuse it across scans.
  - Start at most one scheduler task per process.
  - Cancel and await the scheduler task on shutdown, then close browser sessions and browser resources.
  - Keep Demo mode startup behavior unchanged.
  - Expose only `mode`, scheduler enabled/running state and last batch summary in health; never expose credentials.

- [ ] **Step 4: Run test to verify it passes**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_real_service_lifecycle tests.test_scheduled_scan -v`

  Expected: PASS; no duplicate scheduler and no resource leak on shutdown.

---

### Task 6: 证据清理与 Cookie 摘要接入运行链路

**Files:**

- Create: `app/monitoring/application/evidence_lifecycle.py`
- Modify: `app/monitoring/application/artifact_retention.py`
- Modify: `app/monitoring/adapters/mysql/artifact_repository.py`
- Modify: `app/monitoring/application/scan_product.py`
- Modify: `app/monitoring/api/routes.py`
- Test: `tests/test_evidence_lifecycle.py`
- Modify: `tests/test_artifact_retention.py`

**Interfaces:**

- `async def record_scan_artifacts(scan: Scan, product: Product, repository: ArtifactRepository) -> None`。
- `async def cleanup_scan_artifacts(now: datetime, repository: ArtifactRepository, store: ArtifactStore) -> list[str]`。
- API responses may include artifact references and Cookie summary metadata, but never raw Cookie values.

- [ ] **Step 1: Write the failing test**

  - `test_healthy_artifact_is_replaced_after_next_healthy_scan`
  - `test_unprocessed_exception_expires_after_three_days`
  - `test_resolved_exception_requires_manual_delete`
  - `test_artifact_cleanup_does_not_delete_alert_record`
  - `test_real_scan_api_does_not_return_raw_cookie_value`

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_evidence_lifecycle tests.test_artifact_retention -v`

  Expected: FAIL because the current retention service is not connected to scan persistence and API lifecycle.

- [ ] **Step 3: Implement the lifecycle integration**

  - Record full and ROI Artifact references with each scan.
  - Delete the previous healthy evidence only after the next healthy scan has completed.
  - Retain unprocessed abnormal evidence for 3 days; allow manual deletion only after the alert is resolved.
  - Delete files through `ArtifactStore`, then mark the structured Artifact row deleted; never delete Alert or Scan rows.

- [ ] **Step 4: Run test to verify it passes**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_evidence_lifecycle tests.test_artifact_retention -v`

  Expected: PASS and no raw Cookie value in serialized API data.

---

### Task 7: 真实站点小规模验收和上线门禁

**Files:**

- Create: `docs/real-scan-runbook.md`
- Modify: `docs/production-readiness.md`
- Modify: `config/products.real.example.json`
- Create: `tests/integration/test_real_rollout_gates.py`
- Modify: `Tasks.md`

**Interfaces:**

- Runbook defines a one-product-per-country/platform sequence, required evidence, stop conditions and rollback to Demo mode.
- `test_real_rollout_gates.py` must use local fixtures and fake adapters only; it must never fetch a real external URL.

- [ ] **Step 1: Write the failing gate tests**

  - `test_real_rollout_requires_tesseract_preflight`
  - `test_real_rollout_requires_explicit_catalog_and_database_url`
  - `test_real_rollout_rejects_missing_roi_or_phrase_profile`
  - `test_rollout_can_fall_back_to_demo_mode`

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.integration.test_real_rollout_gates -v`

  Expected: FAIL until the runtime preflight and fallback gates are wired.

- [ ] **Step 3: Implement the rollout gates and runbook**

  - Document Tesseract installation and `eng/deu/ita` verification commands for Windows.
  - Document MySQL migration, backup, restore, timeout and rollback checks.
  - Require explicit authorization before adding real product URLs.
  - Define stop conditions: repeated technical failures, unexpected login/cookie behavior, ROI mismatch, or evidence leakage.
  - Do not mark the 20-product hourly rollout approved until one full observation window passes.

- [ ] **Step 4: Run test to verify it passes**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.integration.test_real_rollout_gates -v`

  Expected: PASS using local fixtures; real-site acceptance remains a documented manual gate.

---

## Final Verification

- [ ] Run all unit and integration-contract tests:

  `uv run --cache-dir .uv-cache python -m unittest discover -s tests -p "test_*.py" -v`

- [ ] Verify lockfile:

  `uv lock --check --cache-dir .uv-cache`

- [ ] Verify Demo startup without Real prerequisites:

  `uv run --cache-dir .uv-cache python app.py`

- [ ] Verify Real preflight with redacted configuration and no real network call.
- [ ] Update `Tasks.md` and `docs/production-readiness.md` with test count, unresolved prerequisites and manual acceptance status.

## Self-Review Results

- **Spec coverage:** The remaining full-PRD gaps map to Task 1 (prerequisites/config), Task 2 (OCR/Cookie semantics), Task 3 (Real bootstrap), Task 4 (MySQL runtime), Task 5 (hourly lifecycle), Task 6 (evidence retention integration), and Task 7 (manual rollout gates).
- **Crawler integration:** Task 2 and Task 3 now make existing crawler screenshots the first Real input path. Live Playwright capture is deliberately later and switchable, so the MVP foundation can be validated without duplicate crawling.
- **Boundary check:** No task adds Kafka, Feishu, automatic inventory mutation, cloud OCR, real checkout actions or distributed execution.
- **Type consistency:** `MonitoringRuntimeConfig` feeds `build_monitoring_container`; the resulting `MonitoringContainer` feeds `create_application` and `monitoring_lifespan`; `HourlyScanRunner` remains the scheduler's only application entrypoint.
- **Verification gaps:** Real website DOM, login state, Tesseract accuracy, MySQL backup/restore and legal/operational authorization remain manual checks by design.
- **Proportion:** The plan focuses on wiring and production gates for already implemented adapters; it does not repeat the completed T7–T16 component work.
