# 商品加购入口库存风险监控 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持当前 MVP 可运行和业务状态一致的前提下，逐步接入真实商品清单、Playwright 截图、ROI、本地 OCR、MySQL、每小时调度和证据生命周期管理。

**Architecture:** 继续使用模块化单体。应用层只依赖 `Scanner`、`OcrEngine`、仓储、证据存储和通知端口；真实实现通过适配器接入，DemoScanner 和内存仓储继续作为 MVP 默认实现。

**Tech Stack:** Python、FastAPI、Playwright、Tesseract 适配器、MySQL 8.x、SQLAlchemy 2.x、Alembic、uv、unittest。

**Spec:** `SPEC.md`

## Global Constraints

- MVP 默认不访问真实商品页面、不调用真实 OCR、不连接 MySQL、不发送飞书或 Kafka。
- `technical_failure` 不得转换为 `inventory_risk`，也不得自动关闭库存风险告警。
- 真实扫描默认覆盖 DE/IT 合计 20 个商品，每小时一次，起步并发不超过 3 个浏览器任务。
- OCR 只处理 ROI，本地优先，完整 Cookie 值不得进入日志、图片元数据或持久化记录。
- 所有 Python 依赖使用 uv 和锁文件管理；MVP 不得因生产依赖缺失而无法启动。
- 不引入微服务、分布式队列、多节点执行或自动修改平台库存。

## Review Focus

- 配置清单中的非法国家、重复市场商品和禁用商品必须得到明确校验；由 T7 覆盖。
- Playwright 页面超时、选择器缺失、截图失败、ROI 失败和 OCR 失败必须映射为技术故障；由 T8–T11 覆盖。
- OCR 词库匹配必须处理大小写、空格、标点、连字符和德意重音；由 T10 覆盖。
- MySQL 活动告警必须保持唯一，重复异常只能更新失败次数和证据；由 T12 覆盖。
- 健康截图、异常截图和 Cookie 摘要必须按生命周期及脱敏规则处理；由 T14 覆盖。

---

> 本文档记录从 MVP 到真实扫描的实现进度。T7–T15 已完成，T16 已完成受控假页面验证；真实站点上线检查仍待人工完成。

## 1. 执行原则

- 先保持当前 MVP 可启动、可测试、可演示，再逐步替换适配器。
- 每个任务都先写失败测试，再实现最小代码，再运行完整测试。
- 领域层不依赖 FastAPI、Playwright、OCR、MySQL 或通知 SDK。
- 真实扫描阶段不得改变 `technical_failure` 与 `inventory_risk` 的边界。
- 不在本计划中加入 Kafka、微服务、分布式队列或自动改库存。
- 生产依赖必须通过 `uv` 和锁文件管理；MVP 不得因生产依赖缺失而无法启动。

## 2. 当前基线

已完成：

- 商品、扫描、告警和复查领域模型。
- DemoScanner 和内存仓储。
- FastAPI API 与本地页面。
- 20 个 DE/IT 商品 fixture。
- 演示结果切换和扫描互斥。
- 商品级按钮锁、Toast、超时恢复、时间记录和浏览器 smoke。

当前验收基线：

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run python -m unittest discover -s tests -p "test_*.py"
```

要求保持全套测试通过，并继续支持：

```powershell
uv run python app.py
```

## 3. 依赖关系

```text
T7 商品清单与配置
  ├── T8 Scanner 端口和真实扫描编排
  │     ├── T9 截图与 ROI
  │     │     └── T10 OCR 与加购词库
  │     └── T11 技术失败重试
  ├── T12 MySQL 持久化
  ├── T13 每小时调度
  └── T14 图片生命周期与 Cookie 摘要

T8–T14
  ↓
T15 真实扫描 API 和运营页面
  ↓
T16 生产验收与切换检查
```

## 4. 任务清单

### T7：商品清单和配置加载

**目标**：把固定 fixture 的输入边界扩展为可校验的 JSON/CSV 商品清单，同时保持 MVP fixture 入口。

**文件边界**：

- Create: `app/monitoring/adapters/product_catalog.py`
- Create: `app/monitoring/config/catalog_schema.py`
- Create: `config/products.example.json`
- Modify: `app/monitoring/api/routes.py`（增加可选配置注入，不改变默认 demo）
- Test: `tests/test_product_catalog.py`

**接口**：

```python
class ProductCatalogLoader(Protocol):
    def load(self, path: str) -> list[Product]: ...
```

**步骤**：

- [x] 写测试：合法 DE/IT 清单加载、禁用商品过滤、重复 `country + platform + sku` 拒绝、非法国家拒绝。
- [x] 运行测试确认在实现前失败。
- [x] 实现 JSON 加载和 Pydantic/纯 Python 校验；CSV 作为同一接口的后续输入格式。
- [x] 运行该模块测试和全套 MVP 测试。

**完成标准**：默认无配置时 MVP 行为不变，配置文件能产生独立的 DE/IT 商品记录。

**实施记录**：已完成 JSON 清单加载、DE/IT 国家校验、禁用商品过滤和 `country + platform + sku` 去重；新增 4 个测试。

### T8：真实 Scanner 端口和扫描编排

**目标**：把真实扫描流程接到现有应用层，不把 Playwright 调用写入 FastAPI 路由。

**文件边界**：

- Modify: `app/monitoring/application/ports.py`
- Modify: `app/monitoring/application/scan_product.py`
- Create: `app/monitoring/adapters/playwright_scanner.py`
- Test: `tests/test_scanner_contract.py`
- Test: `tests/test_playwright_scanner.py`

**接口**：

```python
class Scanner(Protocol):
    async def scan(self, target: ScanTarget) -> ScanObservation: ...
```

**步骤**：

- [x] 写 fake browser 测试：页面成功、导航超时、必要选择器缺失和截图失败分别映射到 observation。
- [x] 运行测试确认失败。
- [x] 实现 `PlaywrightScanner`，复用 `BrowserManager`、`BrowserSession` 和平台注册表。
- [x] 确保每次 observation 都包含最终状态、错误代码和时间信息。
- [x] 运行 scanner 合同测试和完整测试。

**完成标准**：应用层只依赖 `ScanObservation`，DemoScanner 仍能运行。

**实施记录**：已完成 `ScanTarget` 扫描端口、Playwright 页面访问、平台就绪选择器等待、完整截图校验、技术故障码和会话清理；成功页面通过可注入的 observation factory 交给后续 OCR，未配置 OCR 时返回 `OCR_NOT_CONFIGURED`，不会误报健康或关闭告警。新增 6 个测试，全套测试达到 46 个。

### T9：截图和 ROI 适配器

**目标**：保存完整页面截图，并根据平台、页面类型和国家覆盖配置生成 ROI 图片。

**文件边界**：

- Create: `app/monitoring/adapters/roi.py`
- Create: `app/monitoring/adapters/artifact_store_local.py`
- Modify: `app/monitoring/adapters/playwright_scanner.py`
- Create: `config/roi_profiles.example.json`
- Test: `tests/test_roi.py`
- Test: `tests/test_artifact_store.py`

**接口**：

```python
class ArtifactStore(Protocol):
    async def save(self, content: bytes, metadata: ArtifactMetadata) -> ArtifactRef: ...
    async def delete(self, artifact_id: str) -> None: ...
```

**步骤**：

- [x] 写测试：相对比例坐标转换、边界裁剪、无效 ROI、选择器优先和本地路径生成。
- [x] 运行测试确认失败。
- [x] 实现 ROI 裁剪和本地证据保存，路径必须包含国家、平台、SKU 和时间。
- [x] 让技术失败保存必要失败证据，健康截图支持替换引用。
- [x] 运行测试和完整测试。

**完成标准**：ROI 不依赖固定单一像素尺寸，截图路径不包含 Cookie 值。

**实施记录**：已完成相对比例 ROI、CSS 选择器优先、边界裁剪和无效区域校验；新增 `LocalArtifactStore`，证据路径按国家/平台/SKU/日期组织；PlaywrightScanner 支持保存完整截图、ROI 截图并把 ROI 交给后续 OCR。新增 8 个测试。

### T10：本地 OCR 和加购词库

**目标**：只对 ROI 执行本地 OCR，并匹配英、德、意加购词汇。

**文件边界**：

- Create: `app/monitoring/application/phrase_matching.py`
- Create: `app/monitoring/adapters/ocr_tesseract.py`
- Create: `config/phrase_sets.example.json`
- Modify: `app/monitoring/application/ports.py`
- Test: `tests/test_phrase_matching.py`
- Test: `tests/test_ocr_adapter.py`

**接口**：

```python
class OcrEngine(Protocol):
    async def recognize(self, image: ImageRegion) -> OcrResult: ...

def match_add_to_cart(text: str, phrases: list[str]) -> PhraseMatch: ...
```

**步骤**：

- [x] 写词库测试：大小写、空格、标点、连字符、德文和意大利文重音、OCR 变体。
- [x] 写 fake OCR 测试：匹配、无匹配、引擎异常和超时。
- [x] 运行测试确认失败。
- [x] 实现文本归一化和 Tesseract 适配器；真实引擎通过配置启用，MVP 默认不加载。
- [x] 运行测试和完整测试。

**完成标准**：OCR 只接收 ROI，领域判断不依赖 Tesseract 类型。

**实施记录**：已完成英/德/意加购词库加载、大小写/空格/标点/连字符/重音归一化匹配，以及只接收 `ImageRegion` 的 Tesseract 适配器；支持超时、缺少系统二进制和普通引擎异常映射。当前系统仍缺少 Tesseract 可执行程序，因此真实 OCR 尚未启用。新增 8 个测试。

### T11：技术故障重试和扫描周期边界

**目标**：对页面、截图、ROI 和 OCR 技术故障在同一周期最多重试 2 次。

**文件边界**：

- Create: `app/monitoring/application/retry_policy.py`
- Modify: `app/monitoring/application/scan_product.py`
- Test: `tests/test_scan_retry.py`

**接口**：

```python
async def scan_with_retry(scanner: Scanner, target: ScanTarget, attempts: int = 3) -> ScanObservation: ...
```

**步骤**：

- [x] 写测试：首次成功、一次失败后成功、三次失败、有效库存风险不重试。
- [x] 运行测试确认失败。
- [x] 实现退避等待和最终技术故障映射。
- [x] 确保技术故障不创建库存风险告警，也不关闭现有告警。
- [x] 运行测试和完整测试。

**完成标准**：扫描不会永久停留在 `scanning`，重试只针对技术故障。

**实施记录**：已增加 `scan_with_retry`，默认同一周期最多 3 次尝试；技术观察或扫描异常可重试，健康和库存风险立即返回；最终异常继续抛出并由现有用例转为技术故障状态。新增 4 个测试，全套测试达到 66 个。

### T12：MySQL 持久化

**目标**：用 MySQL 作为真实扫描阶段的系统事实来源，保持内存仓储可用于单元测试。

**文件边界**：

- Create: `app/monitoring/adapters/mysql/engine.py`
- Create: `app/monitoring/adapters/mysql/models.py`
- Create: `app/monitoring/adapters/mysql/repositories.py`
- Create: `migrations/versions/001_monitoring_tables.py`
- Modify: `pyproject.toml`、`uv.lock`（仅通过 uv 添加依赖）
- Test: `tests/integration/test_mysql_repositories.py`

**数据表**：

- `products`
- `scan_runs`
- `alerts`
- `alert_transitions`
- `artifacts`
- `roi_profiles`
- `phrase_sets`

**步骤**：

- [x] 写仓储合同测试：商品查询、扫描写入、活动告警唯一性、失败次数更新和状态变更。
- [x] 运行无数据库测试确认合同失败。
- [x] 实现 SQLAlchemy 2.x 模型、Alembic 迁移和 MySQL 仓储。
- [x] 使用显式数据库配置运行集成测试；没有数据库时 MVP 测试仍必须通过。
- [x] 运行全套测试。

**完成标准**：MySQL Session 不泄漏到领域或应用层，MVP 默认仍使用内存仓储。

**实施记录**：已完成 SQLAlchemy 异步引擎、`products/scan_runs/alerts/alert_transitions/artifacts/roi_profiles/phrase_sets` 模型、Alembic 初始迁移和商品/扫描/告警仓储；使用 SQLite 内存数据库完成 4 个仓储合同测试，MVP 仍不连接数据库。新增 `aiosqlite` 作为测试驱动，全套测试达到 70 个。

### T13：每小时调度和有限并发

**目标**：每小时扫描启用商品，起步并发不超过 3 个浏览器任务。

**文件边界**：

- Create: `app/monitoring/application/scheduled_scan.py`
- Create: `app/monitoring/entrypoints/hourly_scan.py`
- Modify: `app/monitoring/runtime_config.py`
- Test: `tests/test_scheduled_scan.py`

**接口**：

```python
class HourlyScanRunner:
    async def run_once(self) -> ScanBatchSummary: ...
```

**步骤**：

- [x] 写测试：只扫描 enabled 商品、最多 3 并发、周期摘要和失败记录。
- [x] 运行测试确认失败。
- [x] 实现单进程调度入口，使用统一时区配置。
- [x] 确保当前周期不能无限阻塞下一周期；超时转技术故障。
- [x] 运行测试和完整测试。

**完成标准**：不引入 Celery、Kafka 或分布式队列即可完成 20 商品每小时扫描。

**实施记录**：已完成 `HourlyScanRunner`、每小时循环入口和配置项；启用商品按最多 3 个并发执行，单商品超时会标记 `technical_failure`，批次返回健康/库存风险/技术故障统计。新增 3 个测试，全套测试达到 73 个。

### T14：图片清理和 Cookie 脱敏摘要

**目标**：按业务规则控制截图生命周期，并保存可审计的 Cookie 摘要。

**文件边界**：

- Create: `app/monitoring/application/artifact_retention.py`
- Create: `app/monitoring/application/cookie_summary.py`
- Modify: `app/monitoring/adapters/artifact_store_local.py`
- Test: `tests/test_artifact_retention.py`
- Test: `tests/test_cookie_summary.py`

**步骤**：

- [x] 写测试：健康截图下一次扫描完成后删除、未处理异常保留 3 天、人工删除恢复异常、完整 Cookie 值不出现在摘要。
- [x] 运行测试确认失败。
- [x] 实现清理策略和 Cookie 名称/域名/路径/过期时间/存在性/哈希摘要。
- [x] 运行测试和完整测试。

**完成标准**：图片删除不删除告警结构化记录，日志和持久化数据无完整 Cookie 值。

**实施记录**：已完成健康证据替换清理、未处理异常 3 天保留、已解决异常人工删除和 Cookie 元数据/哈希摘要；清理服务只删除 Artifact，不修改告警结构化记录。新增 6 个测试。

### T15：真实扫描 API 和运营页面

**目标**：把真实扫描结果接入现有 API 和页面，同时保留 demo 模式。

**文件边界**：

- Modify: `app/monitoring/api/routes.py`
- Modify: `app/monitoring/api/schemas.py`
- Modify: `app/monitoring/templates/index.html`
- Test: `tests/test_real_scan_api.py`
- Test: `tests/test_monitoring_page.py`

**步骤**：

- [x] 写 API 测试：真实配置模式返回扫描时间、OCR、截图引用和技术错误；demo 模式继续支持演示结果接口。
- [x] 运行测试确认失败。
- [x] 增加依赖注入配置，让 API 使用 DemoScanner 或 PlaywrightScanner。
- [x] 页面展示截图证据、OCR 匹配词、错误原因、最近扫描时间和告警状态。
- [x] 运行测试和浏览器 smoke。

**完成标准**：真实模式和 demo 模式边界清晰，页面不暴露完整 Cookie 或凭据。

**实施记录**：已增加 `MonitoringContainer.from_dependencies` 和 `mode`，真实模式 API 返回 OCR、时间和完整/ROI 截图引用，demo-result 仅在 demo 模式开放；本地页面增加证据列。新增 3 个 API 测试，全套测试达到 82 个。

### T16：生产验收与切换检查

**目标**：在真实站点接入前确认数据、安全、性能和回滚条件。

**文件边界**：

- Create: `docs/production-readiness.md`
- Create: `tests/integration/test_real_scan_flow.py`
- Modify: `docs/ARCHITECTURE.md`（记录已验证结论）

**步骤**：

- [x] 使用假的页面和假的 OCR 完成适配器集成测试。
- [ ] 使用少量明确授权的商品做手动站点验收，不把站点数据写入自动化单测。
- [ ] 验证 DE/IT 语言、ROI、词库、技术重试、告警去重和图片清理。
- [ ] 验证 MySQL 备份、恢复、任务超时和回滚到 DemoScanner 的路径。
- [x] 记录未决问题和是否允许扩大到 20 商品每小时扫描。

**完成标准**：真实扫描在受控范围内可重复运行，故障不会误报库存风险，也不会泄露 Cookie 或凭据。

**实施记录**：已完成假页面、假 OCR、ROI、证据保存和技术故障不告警的集成测试；生产站点手动验收、Tesseract 系统二进制、MySQL 备份恢复仍列在 `docs/production-readiness.md`，当前不允许直接扩大到 20 个真实商品。

## 5. 优先级和交付顺序

| 优先级 | 任务 | 交付价值 |
|---|---|---|
| P0 | T7、T8 | 让真实商品输入和 Scanner 边界可替换 |
| P0 | T9、T10 | 完成截图、ROI、本地 OCR 和词库判定 |
| P0 | T11 | 隔离技术故障，避免误报库存风险 |
| P1 | T12 | 提供真实扫描的持久化事实来源 |
| P1 | T13 | 完成每小时扫描 |
| P1 | T14 | 控制截图存储和 Cookie 数据边界 |
| P1 | T15 | 提供生产扫描的接口和运营视图 |
| P0 | T16 | 真实站点上线前的验收和回滚检查 |

## 6. 每个任务的完成定义

任务只有同时满足以下条件才算完成：

- 任务指定的失败测试已先运行并确认失败。
- 最小实现完成后，任务测试和完整测试通过。
- 领域规则没有引入外部适配器依赖。
- MVP 默认启动和 84 个测试继续通过。
- 失败、超时、重复操作和敏感数据边界都有明确验证。
- 变更文件、运行命令和未决风险写入交付记录。

## 7. 当前未决决策

进入真实扫描实现前需要补充：

- MySQL 部署地址、备份策略和连接池参数。
- Tesseract 安装方式和 `eng/deu/ita` 语言包来源。
- 正式商品清单的维护方式和审批流程。
- 真实站点允许的扫描频率和访问条款。
- 任务调度运行环境和时区。
- 运营后台是否需要登录、权限和审计。
- 异常图片正式使用本地磁盘还是对象存储。

## 8. 向爬虫截图数据延展的执行状态

- [x] 增加 `manifest` 输入模式，读取现有爬虫导出的 `path`/`screenshot_path` 截图记录。
- [x] 校验截图路径、商品映射和文件可读性，失败统一进入 `technical_failure`。
- [x] 将截图裁剪为 ROI，接入本地 OCR 结果工厂和 DE/IT 加购词库匹配。
- [x] OCR 匹配成功进入 `healthy`，OCR 成功但未匹配进入 `inventory_risk` 并沿用 MVP 告警逻辑。
- [x] Real/manifest 启动边界、调度生命周期和 Artifact 结构化索引已有受控实现与测试。
- [ ] 安装 Tesseract 系统程序及 `eng/deu/ita` 语言包并完成真实截图识别率验收。
- [ ] 将真实商品目录、截图清单和 MySQL 账号配置接入受控环境后，再开启每小时扫描。

## 9. 监控可视化

- [x] 增加运行模式、截图输入源、OCR 引擎和 Real 前置条件接口。
- [x] 重构 MVP 页面，展示扫描航线、状态统计、筛选、OCR 证据、截图证据和告警操作。
- [x] 增加 Tesseract 与真实截图配置手册。



