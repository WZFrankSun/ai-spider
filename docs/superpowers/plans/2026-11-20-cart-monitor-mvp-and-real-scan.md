# 鍟嗗搧鍔犺喘鍏ュ彛搴撳瓨椋庨櫓鐩戞帶 MVP 涓庣湡瀹炴壂鎻忔帴鍏ュ疄鐜拌鍒?
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 鍦ㄤ笉鐮村潖鐜版湁 Playwright 鐖櫕鍩虹鐨勫墠鎻愪笅锛屽畬鎴愬彲娴嬭瘯鐨?MVP 鐘舵€侀棴鐜紝骞朵负鐪熷疄 Playwright/OCR/MySQL 鎵弿寤虹珛鍙浛鎹㈢殑妯″潡杈圭晫銆?
**Architecture:** 閲囩敤 Python 妯″潡鍖栧崟浣撱€傞鍩熺姸鎬佸拰鍛婅瑙勫垯浣嶄簬妗嗘灦鏃犲叧鐨勬ā鍧楋紝搴旂敤鐢ㄤ緥渚濊禆 `Scanner`銆佷粨鍌ㄥ拰閫氱煡绔彛锛孎astAPI銆佸唴瀛樻紨绀恒€丳laywright銆丱CR銆丮ySQL 鍜岄涔﹂兘浣嶄簬澶栧眰閫傞厤鍣ㄣ€侻VP 鍙惎鐢ㄥ唴瀛樺拰纭畾鎬ф紨绀洪€傞厤鍣紝鐪熷疄鎵弿鑳藉姏浣滀负鍚庣画浠诲姟鎺ュ叆銆?
**Tech Stack:** Python 3.12銆丗astAPI銆乁vicorn銆丳ydantic銆佺幇鏈?Playwright 寮傛 API銆乣unittest`銆傜湡瀹炴寔涔呭寲闃舵浣跨敤 MySQL銆丼QLAlchemy 2.x 鍜?Alembic銆傛湰鍦?OCR 闃舵閫氳繃閫傞厤鍣ㄦ帴鍏?Tesseract锛屽苟淇濈暀鏇挎崲涓哄叾浠栧紩鎿庣殑鑳藉姏銆?
**Spec:** `prd_mvp.md`銆乣docs/ARCHITECTURE.md`銆乣TDD.md`

## Global Constraints

- MVP 瑕嗙洊寰峰浗鍜屾剰澶у埄鍚堣 20 涓潤鎬佸晢鍝併€?- MVP 涓嶈闂湡瀹炲晢鍝侀〉闈紝涓嶄緷璧栧缃戙€丱penAI API銆丱CR 妯″瀷銆丮ySQL 鎴栭涔︺€?- MVP 淇濇寔鏈湴 FastAPI 椤甸潰鍜?HTTP 鎺ュ彛銆?- 鍟嗗搧鐘舵€佸繀椤诲寘鍚?`not_scanned`銆乣scanning`銆乣healthy`銆乣inventory_risk`銆乣technical_failure`銆?- 鎶€鏈晠闅滀笉鑳藉垱寤哄簱瀛橀闄╁憡璀︼紝涔熶笉鑳借嚜鍔ㄥ叧闂凡鏈夊簱瀛橀闄╁憡璀︺€?- 鍚屼竴鍟嗗搧鐨勬寔缁簱瀛樺紓甯稿彧鑳戒繚鐣欎竴涓湭鍏抽棴鍛婅锛屽苟绱 `failure_count`銆?- 鍙湁鏈夋晥鍋ュ悍澶嶆煡鎵嶅彲浠ユ妸搴撳瓨椋庨櫓鍛婅缃负 `resolved`銆?- 婕旂ず缁撴灉蹇呴』鏀寔 `healthy`銆乣inventory_risk`銆乣technical_failure` 鍒囨崲銆?- 鐜版湁 `app/browser`銆乣app/platforms`銆乣app/tools` 鐨勫叕鍏辫涓轰笉寰楀洜 MVP 閲嶆瀯鑰屾敼鍙樸€?- 娴嬭瘯浼樺厛浣跨敤 `.venv\Scripts\python.exe -m unittest`锛屼笉鍋囧畾绯荤粺 Python 瀹夎 pytest銆?- 鏈緱鍒扮敤鎴锋巿鏉冿紝涓嶆墽琛?commit銆乸ush銆佽縼绉绘垨鐪熷疄绔欑偣鎵弿銆?
## Review Focus

- 鏈夋晥鎵弿缂哄皯鍔犺喘璇嶆椂蹇呴』鍒涘缓搴撳瓨鍛婅锛屾妧鏈晠闅滀笉鑳藉垱寤鸿鍛婅銆傜敱浠诲姟 2 鐨勯鍩熸祴璇曞浐瀹氥€?- 鍚屼竴鍟嗗搧閲嶅鎵弿涓嶈兘鍒涘缓閲嶅娲诲姩鍛婅銆傜敱浠诲姟 2 鐨勫憡璀﹀幓閲嶆祴璇曞浐瀹氥€?- 鍟嗗搧鎵弿鏈熼棿蹇呴』杩涘叆 `scanning`锛岀浜屾鎵弿蹇呴』琚嫆缁濇垨杩斿洖鍐茬獊銆傜敱浠诲姟 3 鐨勫苟鍙戞祴璇曞浐瀹氥€?- 鎶€鏈晠闅滃鏌ヤ笉鑳芥妸鍛婅鏍囪涓?`resolved`銆傜敱浠诲姟 2 鍜屼换鍔?3 鐨勫鏌ユ祴璇曞浐瀹氥€?- 婕旂ず缁撴灉鍒囨崲蹇呴』闅旂涓嶅悓搴旂敤瀹炰緥锛屼笉鑳芥薄鏌撳叾浠栨祴璇曘€傜敱浠诲姟 3 鐨?API 娴嬭瘯鍥哄畾銆?
---

## 鐜版湁鏂囦欢涓庣洰鏍囨枃浠?
### 鐜版湁浠ｇ爜

- `app.py`锛氬綋鍓?Uvicorn 鍚姩鍏ュ彛銆?- `app/mvp/models.py`锛氬綋鍓嶆紨绀烘ā鍨嬨€?- `app/mvp/store.py`锛氬綋鍓嶅唴瀛?fixture 鍜屾紨绀虹姸鎬併€?- `app/mvp/api.py`锛氬綋鍓?FastAPI 璺敱銆?- `app/mvp/templates/index.html`锛氬綋鍓嶆湰鍦伴〉闈€?- `app/browser/*`锛氱幇鏈夋祻瑙堝櫒浼氳瘽鍜岀敓鍛藉懆鏈熺鐞嗐€?- `app/platforms/*`锛氱幇鏈夊钩鍙?YAML 閰嶇疆鍜屽钩鍙版敞鍐岃〃銆?- `app/tools/browser/screenshot.py`锛氱幇鏈夐〉闈㈠氨缁拰鎴浘宸ュ叿銆?- `tests/test_mvp_store.py`銆乣tests/test_mvp_api.py`锛氬綋鍓?MVP 娴嬭瘯銆?
### 鐩爣妯″潡

- `app/monitoring/domain/`锛氬晢鍝併€佹壂鎻忋€佸憡璀︾姸鎬佸拰涓氬姟瑙勫垯銆?- `app/monitoring/application/`锛氭壂鎻忋€佸鏌ャ€佸垪琛ㄦ煡璇㈢瓑鐢ㄤ緥鍜岀鍙ｃ€?- `app/monitoring/adapters/`锛氭紨绀恒€丳laywright銆丱CR銆丮ySQL銆佹枃浠跺拰閫氱煡閫傞厤鍣ㄣ€?- `app/monitoring/api/`锛氱湡瀹炴壂鎻忛樁娈电殑 HTTP 璺敱鍜岃姹傛ā鍨嬨€?
MVP 鍙互鍏堣 `app/mvp` 浣滀负鍏煎鍏ュ彛锛岄€愭鎶婇鍩熻鍒欒縼绉诲埌 `app/monitoring`锛岄伩鍏嶄竴娆℃€ч噸鏋勭幇鏈夌埇铏€?
## Task 1: 寤虹珛棰嗗煙鐘舵€佹ā鍨嬪拰涓嶅彲鍙樿鍒?
**Files:**

- Create: `app/monitoring/__init__.py`
- Create: `app/monitoring/domain/__init__.py`
- Create: `app/monitoring/domain/models.py`
- Create: `app/monitoring/domain/policies.py`
- Create: `tests/test_monitoring_domain.py`

**Interfaces:**

- `ProductScanStatus`: `not_scanned | scanning | healthy | inventory_risk | technical_failure`
- `AlertType`: `PRODUCT_ADD_TO_CART_MISSING | MONITORING_TECHNICAL_FAILURE`
- `AlertStatus`: `open | acknowledged | pending_verification | resolved | reopened`
- `Product(id: str, country: str, platform: str, sku: str, url: str, page_type: str, roi_profile_id: str, enabled: bool)`
- `ScanObservation(status: ProductScanStatus, ocr_text: str, matched_phrase: str | None, confidence: float | None, error_code: str | None, error_message: str | None)`
- `Alert.apply_observation(observation: ScanObservation) -> Alert`
- `can_resolve_alert(alert: Alert, observation: ScanObservation) -> bool`

- [x] **Step 1: Write the failing tests**

  Add tests for:

  - New products start as `not_scanned`.
  - A healthy observation produces `healthy` and preserves the matched phrase.
  - An observation without a matched phrase produces `inventory_risk`.
  - A technical failure produces `technical_failure` and no inventory-risk resolution.
  - A technical failure cannot make an alert `resolved`.
  - Only a healthy verification can resolve an inventory-risk alert.

- [x] **Step 2: Run the tests and verify the expected failure**

  Run:

  ```powershell
  .venv\Scripts\python.exe -m unittest tests.test_monitoring_domain -v
  ```

  Expected: import or symbol failures because `app.monitoring` does not exist yet.

- [x] **Step 3: Implement the domain models and policies**

  Keep these modules free of FastAPI, Playwright, SQLAlchemy, OCR and notification imports. Use plain Python value objects or Pydantic models only where validation is part of the domain input.

- [x] **Step 4: Run the focused tests**

  Expected: all domain state and resolution tests pass.

- [x] **Step 5: Review the diff and await commit authorization**

## Task 2: Implement the application ports and deterministic scan use case

**Files:**

- Create: `app/monitoring/application/__init__.py`
- Create: `app/monitoring/application/ports.py`
- Create: `app/monitoring/application/scan_product.py`
- Create: `app/monitoring/application/verify_alert.py`
- Create: `app/monitoring/adapters/__init__.py`
- Create: `app/monitoring/adapters/demo_scanner.py`
- Create: `app/monitoring/adapters/memory_repositories.py`
- Create: `tests/test_monitoring_use_cases.py`

**Interfaces:**

- `class Scanner(Protocol): async def scan(self, product: Product) -> ScanObservation`
- `class ProductRepository(Protocol): async def get(self, product_id: str) -> Product | None; async def list_enabled(self) -> list[Product]`
- `class ScanRepository(Protocol): async def add(self, scan: Scan) -> None; async def latest_for(self, product_id: str) -> Scan | None`
- `class AlertRepository(Protocol): async def find_active_inventory_alert(self, product_id: str) -> Alert | None; async def save(self, alert: Alert) -> None; async def get(self, alert_id: str) -> Alert | None`
- `class ScanProduct: async def execute(self, product_id: str) -> ScanSummary`
- `class VerifyAlert: async def execute(self, alert_id: str) -> Alert`
- `class DemoScanner: async def scan(self, product: Product) -> ScanObservation`

- [x] **Step 1: Write the failing use-case tests**

  Add tests for:

  - `DemoScanner` returns inventory risk for `DE-001` and `IT-001`, healthy for the other fixture products.
  - A first inventory-risk scan creates one alert.
  - A repeated inventory-risk scan updates the same alert and increments `failure_count`.
  - A technical failure records a technical result without creating an inventory alert.
  - Healthy verification resolves the alert.
  - Technical-failure verification leaves the alert unresolved.
  - Unknown product and unknown alert raise explicit domain/application errors.

- [x] **Step 2: Run the focused tests and verify they fail**

  Run:

  ```powershell
  .venv\Scripts\python.exe -m unittest tests.test_monitoring_use_cases -v
  ```

- [x] **Step 3: Implement ports, memory repositories and `ScanProduct`**

  The use case owns the order of operations: load product, reject disabled or already-scanning work, persist the scanning state, call `Scanner`, persist the result, then apply alert policy. The scanner must not create alerts itself.

- [x] **Step 4: Implement `VerifyAlert`**

  Mark the alert as `pending_verification`, force one scanner call, and resolve only from a healthy observation. Keep the alert pending on technical failure and reopen it on a valid inventory-risk observation.

- [x] **Step 5: Run focused and full tests**

  Run:

  ```powershell
  .venv\Scripts\python.exe -m unittest tests.test_monitoring_domain tests.test_monitoring_use_cases -v
  .venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
  ```

  Expected: the new domain/use-case tests and existing tests pass.

## Task 3: Add demo-result switching and scan mutual exclusion

**Files:**

- Modify: `app/monitoring/adapters/demo_scanner.py`
- Modify: `app/monitoring/application/scan_product.py`
- Modify: `app/monitoring/adapters/memory_repositories.py`
- Create: `tests/test_monitoring_demo_controls.py`

**Interfaces:**

- `DemoScanner.set_next_result(product_id: str, status: ProductScanStatus) -> None`
- `DemoScanner.clear_next_result(product_id: str) -> None`
- `ScanProduct.execute(product_id: str) -> ScanSummary`
- `ScanInProgressError(product_id: str)`

- [x] **Step 1: Write the failing tests**

  Add tests for:

  - Setting the next result to `healthy`, `inventory_risk` or `technical_failure` changes only the next scan.
  - A new store has no pending demo overrides.
  - A product is `scanning` while its scanner operation is awaiting completion.
  - A second scan for the same product raises `ScanInProgressError`.
  - A completed scan clears the scanning marker even when the scanner raises an exception.

- [x] **Step 2: Run tests and verify the expected failure**

  Run:

  ```powershell
  .venv\Scripts\python.exe -m unittest tests.test_monitoring_demo_controls -v
  ```

- [x] **Step 3: Implement isolated demo overrides and an explicit in-progress registry**

  Keep overrides in the adapter/store instance. Do not use module-level mutable state so each `create_app()` receives an isolated demo.

- [x] **Step 4: Run focused and full tests**

  Expected: demo switching and mutual-exclusion tests pass, and existing tests still pass.

## Task 4: Move FastAPI routes to the application use cases

**Files:**

- Create: `app/monitoring/api/__init__.py`
- Create: `app/monitoring/api/routes.py`
- Create: `app/monitoring/api/schemas.py`
- Modify: `app/mvp/api.py`
- Modify: `app.py`
- Create: `tests/test_monitoring_api.py`

**Interfaces:**

- `create_monitoring_app(container: MonitoringContainer | None = None) -> FastAPI`
- `GET /api/health`
- `GET /api/products`
- `GET /api/scans`
- `GET /api/alerts`
- `POST /api/products/{product_id}/scan`
- `POST /api/products/{product_id}/demo-result`
- `POST /api/alerts/{alert_id}/verify`

- [x] **Step 1: Write the failing API contract tests**

  Cover health, 20 products, initial `not_scanned`, demo result switching, scan status, alert deduplication, verification, technical-failure boundaries, and 404 responses.

- [x] **Step 2: Run the API tests and verify failure**

  Run:

  ```powershell
  .venv\Scripts\python.exe -m unittest tests.test_monitoring_api -v
  ```

- [x] **Step 3: Implement route schemas and a dependency container**

  Routes translate HTTP input to use-case requests and translate domain/application errors to 404, 409, or 422 responses. They must not call Playwright, OCR, repositories, or mutate alerts directly.

- [x] **Step 4: Preserve the current entry point**

  Keep `python app.py` as the local startup command. Existing endpoint behavior that remains in the MVP PRD must continue to work while the route implementation moves behind use cases.

- [x] **Step 5: Run focused and full API tests**

  Expected: all API contract tests and the existing suite pass.

## Task 5: Update the demo page for the complete state model

**Files:**

- Modify: `app/mvp/templates/index.html`
- Create: `tests/test_mvp_page.py`

**Interfaces:**

- The page consumes the API endpoints from Task 4.
- Display labels map `not_scanned`, `scanning`, `healthy`, `inventory_risk`, and `technical_failure` to user-facing Chinese text.

- [x] **Step 1: Write the failing page contract tests**

  Without requiring a browser, assert that `/` contains the result switch control, the `scanning`/`not_scanned` labels, technical-failure text, product table, alert table and verification action.

- [x] **Step 2: Run page tests and verify failure**

  Run:

  ```powershell
  .venv\Scripts\python.exe -m unittest tests.test_mvp_page -v
  ```

- [x] **Step 3: Implement the UI behavior**

  Add a per-product result selector and disable the scan button while a request is active. Render technical failure separately from inventory risk. Do not add authentication, charts, pagination or a frontend build system.

- [x] **Step 4: Run page tests and perform a manual browser smoke test**

  Verify the flow `not_scanned 鈫?scanning 鈫?inventory_risk 鈫?pending_verification 鈫?resolved`, plus the technical-failure path that does not close the alert.

## Task 6: Verify the MVP slice and update operational documentation

**Files:**

- Modify: `prd_mvp.md` only if implementation behavior needs a documented correction
- Modify: `TDD.md` only if test commands or coverage change
- Modify: `TASK.md` only to mark completed tasks
- Create: `docs/superpowers/plans/2026-11-20-cart-monitor-mvp-and-real-scan.md` is this plan; do not overwrite it during execution

- [x] **Step 1: Run the complete test suite**

  ```powershell
  .venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
  ```

  Expected: zero failures and zero unhandled errors.

- [x] **Step 2: Start the local service**

  ```powershell
  .venv\Scripts\python.exe app.py
  ```

  Verify `GET /api/health` returns `status=ok` and `mode=demo`.

- [x] **Step 3: Exercise the business flow through HTTP**

  Verify 20 products, result switching, one-alert deduplication, technical-failure isolation and healthy verification.

- [x] **Step 4: Inspect the diff and document gaps**

  Confirm no real URL access, OCR model, MySQL connection, Feishu token or complete Cookie enters the MVP. Record any remaining gap in the final report.


## Execution status

Tasks 1–6 completed. Tasks 7–9 remain deferred post-MVP.

## Task 7: Add MySQL persistence (deferred, post-MVP)

**Files:**

- Modify: `pyproject.toml` to add SQLAlchemy 2.x and Alembic only after explicit approval
- Create: `app/monitoring/adapters/mysql/engine.py`
- Create: `app/monitoring/adapters/mysql/models.py`
- Create: `app/monitoring/adapters/mysql/repositories.py`
- Create: `alembic/versions/<initial_revision>.py`
- Create: `tests/integration/test_mysql_repositories.py`

**Interfaces:**

- Implement the repository protocols from Task 2.
- Preserve the same domain objects and use-case signatures.

- [ ] Write repository contract tests against a disposable MySQL instance.
- [ ] Add migrations for `products`, `scan_runs`, `alerts`, `alert_transitions`, `artifacts`, `roi_profiles` and `phrase_sets`.
- [ ] Verify unique active inventory alert behavior under a transaction.
- [ ] Run unit tests without MySQL and integration tests with explicit database configuration.

This task is outside the current MVP because `prd_mvp.md` explicitly keeps the demo in memory.

## Task 8: Add real Playwright and local OCR adapters (deferred, post-MVP)

**Files:**

- Create: `app/monitoring/adapters/playwright_scanner.py`
- Create: `app/monitoring/adapters/ocr_tesseract.py`
- Create: `app/monitoring/adapters/artifacts_local.py`
- Create: `app/monitoring/config/roi_profiles.py`
- Create: `app/monitoring/config/phrase_sets.py`
- Create: `tests/integration/test_real_scan_adapters.py`

**Interfaces:**

- Implement `Scanner.scan(product) -> ScanObservation`.
- Implement `OcrEngine.recognize(image) -> OcrResult`.
- Reuse `BrowserManager`, `BrowserSession`, platform profiles and existing screenshot readiness behavior.

- [ ] Write fake-page and fake-OCR tests for page timeout, missing selectors, screenshot failure, ROI failure, OCR failure, no phrase and phrase match.
- [ ] Implement Playwright navigation, fixed viewport, wait conditions, Cookie handling and ROI artifact creation.
- [ ] Implement local Tesseract recognition and phrase normalization for English, German and Italian.
- [ ] Run adapter tests without real sites, then perform manual site validation separately.

This task must not leak Playwright or OCR types into the domain layer.

## Task 9: Add hourly scheduling and future notifications (deferred, post-MVP)

**Files:**

- Create: `app/monitoring/scheduler/hourly.py`
- Create: `app/monitoring/adapters/notifier_null.py`
- Create: `app/monitoring/adapters/notifier_feishu.py` only after explicit notification approval
- Create: `tests/test_monitoring_scheduler.py`

**Interfaces:**

- `HourlyScanRunner.run_once() -> ScanBatchSummary`
- `Notifier.notify(event: AlertEvent) -> None`

- [ ] Test that one run reads enabled products and invokes `ScanProduct` once per product.
- [ ] Test scheduler-level timeout and partial failure reporting.
- [ ] Keep notification failures from changing domain alert status.
- [ ] Add Feishu delivery only after webhook credentials and message ownership are explicitly approved.

This task is outside the MVP because the current PRD requires manual demo scans.

## Self-review

### Spec coverage

- MVP local service: Tasks 4鈥?.
- 20 DE/IT products: Tasks 2鈥?.
- Five product states and `scanning` lock: Tasks 1鈥?.
- Demo result switching: Tasks 3鈥?.
- Alert deduplication and verification: Tasks 1鈥?.
- Technical-failure isolation: Tasks 1鈥?.
- No real external dependency in MVP: Global Constraints and Task 6.
- MySQL system-of-record design: Task 7 and `docs/ARCHITECTURE.md`.
- Playwright/OCR replaceable seams: Task 8 and `docs/ARCHITECTURE.md`.
- Hourly scheduling and future Feishu: Task 9.

### Deliberate gaps

- Real MySQL, Playwright, OCR and scheduler implementation is deferred because it is outside the current MVP PRD.
- The plan does not select a final production OCR engine beyond the adapter-first Tesseract recommendation. A real screenshot benchmark must validate that choice.
- Production product count and scan duration are unknown, so queue and concurrency scaling remain deferred.

### Type consistency

- All use cases consume `Product`, `ScanObservation`, and repository/scanner protocols from the application layer.
- API routes call use cases, never concrete scanner or repository adapters.
- `DemoScanner` and future `PlaywrightScanner` implement the same `Scanner` protocol.
- MySQL repositories implement the same protocols as memory repositories.

### Handoff

This plan is ready for review. No code changes are included in this plan-writing step.

