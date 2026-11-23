# 监控可视化与真实截图输入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于现有 MVP 数据接口，完成监控页面的完整可视化展示，并准备可读取爬虫截图、执行 ROI OCR 和展示证据的本地 Real/manifest 运行环境。

**Architecture:** 保留现有 FastAPI 模块化单体和 `/api/products`、`/api/scans`、`/api/alerts`、`/api/health` 接口。前端只消费接口，不复制业务判断；后端补充运行状态和 Real 前置条件信息接口。Real 模式第一阶段读取爬虫截图清单，使用现有 `CrawlerScreenshotScanner`、ROI、OCR 和告警链路；Playwright 实时截图继续作为可切换输入。

**Tech Stack:** Python 3.12、uv、FastAPI、HTML/CSS/JavaScript、Playwright、Pillow、pytesseract/Tesseract、unittest。

**Spec:** `prd_mvp.md`、`SPEC.md`、`docs/ARCHITECTURE.md`、`docs/real-scan-runbook.md`

## Global Constraints

- MVP Demo 默认继续可启动，不依赖 Tesseract、MySQL、Kafka 或飞书。
- Real/manifest 模式只读取明确授权的爬虫截图，不模拟德国本地访问环境。
- OCR 只处理 ROI；匹配加购词为 `healthy`，未匹配为 `inventory_risk`，读取失败或 OCR 失败为 `technical_failure`。
- 完整 Cookie 值不得出现在页面、日志、Artifact 元数据或 API 响应中。
- 不自动点击真实加购，不修改平台库存，不执行下单。
- 所有 Python 依赖由 uv 管理；不新增 Kafka、Celery 或分布式队列。
- Tesseract 系统程序和语言包可以下载，但必须记录安装路径和版本，不把安装器提交到项目目录。

## Review Focus

- Demo 页面在没有 Real 配置时仍能正常展示 20 个演示商品。
- Real 模式缺少 Tesseract、截图清单或配置文件时，页面显示明确的阻塞原因。
- OCR 匹配、未匹配、技术故障三种状态在统计卡片、商品列表、证据区和告警区保持一致。
- 截图路径、ROI 路径和 Cookie 摘要展示不能泄露敏感值或允许路径越界。
- 长 OCR 文本、空截图、无扫描记录和大量商品在窄屏下仍可阅读和操作。

---

## 文件边界

### 新增

- `tests/test_monitoring_status_api.py`：运行模式、输入源和 Real 前置条件接口测试。
- `docs/real-input-setup.md`：Tesseract、截图清单、商品目录和 ROI 配置准备手册。

### 修改

- `app/monitoring/api/routes.py`：新增只读的 `/api/monitoring/status`，返回模式、输入源、调度状态、OCR 配置摘要和前置条件结果；不返回密码或完整连接串。
- `app/mvp/templates/index.html`：重新设计监控页面，展示运行概览、风险分布、按国家/平台筛选、OCR 证据、截图路径、扫描时间、耗时、告警复查和错误原因。
- `app/monitoring/runtime_config.py`：补充配置摘要和前置条件序列化函数，确保页面可消费。
- `.env.example`：补充截图根目录、manifest、Real 模式和 Tesseract 配置示例。
- `Tasks.md`、`docs/production-readiness.md`：记录可视化和真实截图输入状态。

---

### Task 1: 运行状态与前置条件 API

**Files:**

- Modify: `app/monitoring/runtime_config.py`
- Modify: `app/monitoring/api/routes.py`
- Test: `tests/test_monitoring_status_api.py`

**Interfaces:**

- `def monitoring_status(config: MonitoringRuntimeConfig) -> dict`：返回 `mode`、`input_mode`、`scheduler_enabled`、`scheduler_running`、`ocr.engine`、`ocr.languages`、`preflight.ready`、`preflight.missing`。
- `GET /api/monitoring/status`：不返回数据库密码、完整 URL、Cookie 或本机绝对路径中的敏感目录。

- [ ] **Step 1: Write the failing tests**

  - `test_demo_status_is_ready_without_tesseract`
  - `test_real_status_lists_missing_tesseract_and_files`
  - `test_status_does_not_include_database_credentials`

- [ ] **Step 2: Run tests and verify failure**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_monitoring_status_api -v`

  Expected: FAIL because the status endpoint and serializer do not exist.

- [ ] **Step 3: Implement the minimal status serializer and endpoint**

  Demo mode returns ready state without probing external services. Real mode uses existing prerequisite validation and only exposes redacted, user-actionable messages.

- [ ] **Step 4: Run focused tests and the existing API tests**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_monitoring_status_api tests.test_monitoring_api tests.test_real_scan_api -v`

  Expected: PASS.

---

### Task 2: 前端信息架构和视觉重构

**Files:**

- Modify: `app/mvp/templates/index.html`
- Modify: `tests/test_mvp_page.py`

**Interfaces:**

- 页面加载 `/api/health`、`/api/monitoring/status`、`/api/products`、`/api/scans`、`/api/alerts`。
- 页面保留现有扫描、演示结果设置和告警复查操作。
- 前端状态展示使用接口返回值，不自行推断库存状态。

**Visual direction:**

- Palette: `#0E1B2A` 工作台深蓝、`#F5F7F4` 雾白背景、`#1C9A78` 健康青绿、`#D97732` 风险琥珀、`#C94B4B` 故障红、`#DCE4EA` 边界灰。
- Type: 使用 `Inter`/系统无衬线作为数据正文，使用 `Source Serif 4` 作为页面主标题，形成运营工具的编辑感和可读层级。
- Layout: 顶部是运行状态和当前扫描来源；第二层是风险总览；主区域是可筛选商品表格；右侧或下方展示告警队列和证据详情。
- Distinctive element: 用“扫描航线”横向状态条呈现 `截图输入 → ROI → OCR → 判断 → 告警`，每个节点显示当前状态。
- Accessibility: 键盘焦点、移动端横向表格、`aria-live` 消息、`prefers-reduced-motion` 保持有效。

- [ ] **Step 1: Write failing page assertions**

  - `test_page_contains_monitoring_status_panel`
  - `test_page_contains_ocr_evidence_and_screenshot_columns`
  - `test_page_keeps_scan_and_verify_controls`

- [ ] **Step 2: Run page tests and verify failure**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_mvp_page -v`

  Expected: FAIL because the new status panel and pipeline visualization do not exist.

- [ ] **Step 3: Implement the visual redesign**

  Keep the page as a single local HTML template to preserve MVP deployment simplicity. Add status, pipeline, filters, evidence expansion and empty/error states. Use CSS variables and component-specific selectors; avoid generic card repetition.

- [ ] **Step 4: Run page and full tests**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_mvp_page tests.test_mvp_api tests.test_monitoring_api -v`

  Expected: PASS.

---

### Task 3: 爬虫截图输入配置示例和本地验证工具

**Files:**

- Create: `docs/real-input-setup.md`
- Modify: `config/products.real.example.json`
- Modify: `config/screenshots.manifest.example.json`
- Modify: `.env.example`
- Test: `tests/integration/test_real_rollout_gates.py`

**Interfaces:**

- 提供清晰的配置复制路径：`products.real.json`、`screenshots.manifest.json`、`roi_profiles.json`、`phrase_sets.json`。
- manifest 支持现有爬虫的 `path` 和 `screenshot_path` 字段。
- 配置验证只使用本地文件，不访问外部电商网站。

- [ ] **Step 1: Write failing configuration gate tests**

  - `test_example_manifest_maps_to_example_catalog`
  - `test_real_gate_rejects_missing_screenshot_root`
  - `test_demo_gate_remains_available_without_tesseract`

- [ ] **Step 2: Run tests and verify failure**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.integration.test_real_rollout_gates -v`

  Expected: FAIL until the examples and setup validation are aligned.

- [ ] **Step 3: Add setup documentation and safe examples**

  Document Windows Tesseract installation, `tesseract --version`, language package verification, screenshot manifest generation, ROI coordinates and manual one-product acceptance. Use placeholder URLs only.

- [ ] **Step 4: Run local gate tests**

  Run: `uv run --cache-dir .uv-cache python -m unittest tests.integration.test_real_rollout_gates -v`

  Expected: PASS without network access.

---

### Task 4: Tesseract 和真实截图资源准备

**Files:**

- Modify: `docs/production-readiness.md`
- Modify: `docs/real-input-setup.md`

- [ ] **Step 1: Check/download Tesseract**

  Use the official Windows distribution source, install the executable and `eng/deu/ita` language data outside the repository, then record the path and version in the setup document.

- [ ] **Step 2: Prepare local configuration**

  Copy the example catalog and manifest to local files, place authorized screenshots under the configured root, and fill ROI and phrase files.

- [ ] **Step 3: Run preflight**

  Run: `uv run --cache-dir .uv-cache python -c "from app.monitoring.runtime_config import load_monitoring_config, validate_real_prerequisites; c=load_monitoring_config(); print(validate_real_prerequisites(c))"`

  Expected: Demo returns `[]`; Real returns no missing prerequisite only after local resources are installed and configured.

---

## Final Verification

- [ ] `uv run --cache-dir .uv-cache python -m unittest discover -s tests -p "test_*.py" -q`
- [ ] `uv lock --check --cache-dir .uv-cache`
- [ ] `uv run --cache-dir .uv-cache python app.py` starts Demo mode.
- [ ] Browser view shows the status panel, pipeline, filters, evidence and alerts.
- [ ] Real preflight output is redacted and contains no credentials.

## Self-Review

- MVP behavior is preserved through the existing API controls.
- The page consumes current APIs and adds one read-only status API for the data that was previously invisible.
- Real screenshot ingestion remains local and manifest based; no external website is required for tests.
- Tesseract download is an environment step and its installer is not stored in the repository.
