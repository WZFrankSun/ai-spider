# 商品加购入口库存风险监控 Agent Specification

## 1. 文档目的

本文档把完整 PRD、当前 MVP PRD、架构设计和 TDD 约束合并为一份可执行规格。

本文档使用两个阶段描述产品：

- **MVP 阶段**：当前已经实现的本地演示，用静态商品和确定性结果验证“扫描、告警、复查、恢复”闭环。
- **真实扫描阶段**：MVP 验证后接入现有 Playwright 爬虫、截图、ROI、本地 OCR、MySQL 和每小时调度。

真实扫描阶段不得改变 MVP 已确认的业务状态含义和告警边界。

## 2. 业务目标

跨境电商运营人员需要提前发现德国和意大利市场商品详情页无法加入购物车的问题。系统通过检查加入购物车区域是否出现目标词汇，发现可能由库存数据或平台运营配置造成的销售风险。

系统只负责发现、记录和复查风险，不自动修改平台库存，也不执行真实加购或下单。

目标市场为德国和意大利，首批规模为两国合计 20 个商品，建议每国约 10 个。真实扫描阶段默认每小时执行一次。

## 3. 阶段范围

### 3.1 当前 MVP：已实现范围

MVP 使用 FastAPI 本地服务、内存商品 fixture 和 `DemoScanner`：

- 20 个静态商品，德国 10 个、意大利 10 个。
- 商品状态：`not_scanned`、`scanning`、`healthy`、`inventory_risk`、`technical_failure`。
- 确定性模拟健康、库存风险和技术故障。
- 模拟 OCR 文本和加购词匹配结果。
- 库存风险告警创建、去重和失败次数累计。
- 告警复查、恢复和重新打开。
- 商品扫描、扫描历史、告警和健康检查 API。
- 本地 HTML/JavaScript 演示页面。
- 商品级操作锁、请求超时、Toast 消息、时间记录和重复操作保护。

MVP 启动不依赖真实商品页面、外网、OpenAI API Key、OCR 模型、MySQL、Kafka 或飞书。

### 3.2 真实扫描阶段：后续实现范围

后续实现替换或扩展扫描适配器，但保持应用层和领域层接口稳定：

- 读取版本化 JSON 或 CSV 商品清单。
- 复用现有 `BrowserManager`、`BrowserSession`、平台 YAML 和截图工具。
- 使用固定视口、语言环境、等待条件和 Cookie 弹窗处理。
- 保存完整页面截图并按 ROI 配置裁剪加入购物车区域。
- 使用本地 OCR 识别英文、德文和意大利文。
- 采用国家、平台、页面类型对应的加购词库。
- 技术故障同一周期重试 2 次，三次失败后记录技术故障。
- 每小时扫描启用商品，有限并发不超过 3 个浏览器任务起步。
- 使用 MySQL 保存商品、扫描、告警、状态变更和证据索引。
- 按规则清理健康截图，保留未处理异常证据最多 3 天。
- 保存脱敏 Cookie 摘要，不保存完整 Cookie 值。

### 3.3 明确不属于当前范围

- 自动修改 Amazon、Shopify 或其他平台库存。
- 通过真实点击加入购物车验证完整下单链路。
- 使用 IP 地理位置模拟德国或意大利访问。
- 自动发现全站商品。
- 将商品截图上传到云端 OCR。
- 移动端视口扫描。
- 微服务、分布式队列、多节点执行或复杂事件总线。
- 当前 MVP 接入飞书 Webhook。

## 4. 用户和核心流程

### 4.1 用户角色

- 运营人员：查看异常、调整平台库存、发起复查和删除已处理证据。
- 库存管理人员：处理库存数据和销售状态。
- 技术人员：维护商品清单、平台配置、ROI 和词库，处理技术故障。

### 4.2 MVP 流程

```text
打开本地页面
  → 查看 20 个商品和当前告警
  → 选择演示结果
  → 点击立即扫描
  → 查看商品状态和模拟 OCR 结果
  → 发现库存风险告警
  → 标记已处理并验证
  → 查看复查后的 resolved 或 reopened 状态
```

### 4.3 真实扫描流程

```text
读取商品清单
  → 加载国家/平台/页面配置
  → 打开商品页面
  → 等待页面与商品区域
  → 处理弹窗并截图
  → 裁剪 ROI
  → 本地 OCR
  → 归一化并匹配词库
  ├─ 匹配成功：healthy
  ├─ 有效扫描但未匹配：inventory_risk
  └─ 页面、截图、ROI 或 OCR 失败：technical_failure
```

## 5. 状态和业务规则

### 5.1 商品扫描状态

| 状态 | 含义 |
|---|---|
| `not_scanned` | 尚未执行过扫描 |
| `scanning` | 当前正在执行扫描 |
| `healthy` | 有效扫描识别到加入购物车入口 |
| `inventory_risk` | 有效扫描未识别到加入购物车入口 |
| `technical_failure` | 页面或识别环节失败，结果不可判定 |

状态流转：

```text
not_scanned → scanning → healthy
                       ├→ inventory_risk
                       └→ technical_failure
```

约束：

- `technical_failure` 不得转换为 `inventory_risk`。
- 同一商品同时只能存在一个扫描操作。
- 技术故障不能自动关闭已有库存风险告警。
- 只有有效扫描并识别到目标词汇，才允许恢复库存风险告警。
- MVP 和真实扫描阶段都必须提供开始时间、结束时间和最终状态。

### 5.2 告警类型

- `PRODUCT_ADD_TO_CART_MISSING`：有效页面和 OCR 成功，但没有匹配任何加购词。
- `MONITORING_TECHNICAL_FAILURE`：页面、等待、截图、ROI 或 OCR 失败。

### 5.3 告警状态

```text
open → acknowledged → pending_verification → resolved
                                      └──────→ reopened
```

完整实现可以增加 `expired`，但在当前 MVP 和首个真实扫描版本中不自动过期告警；图片保留期限与告警状态分开处理。

规则：

- 首次库存异常创建 `open` 告警。
- 同一国家、平台、SKU 和告警类型只有一个活动告警。
- 持续异常更新 `failure_count`、最近时间和最近证据，不重复创建活动告警。
- 运营处理后进入 `pending_verification`。
- 有效健康复查进入 `resolved`。
- 复查仍为库存风险进入 `reopened`。
- 技术故障复查保持 `pending_verification`，不得进入 `resolved`。
- 已恢复后再次发生异常时创建新的活动告警，并保留历史关联。

## 6. 商品配置

真实扫描阶段使用版本化 JSON 或 CSV 清单。每个国家市场中的商品是一条独立监控记录，即使两个市场暂时使用相同 URL，也不能合并记录。

```json
{
  "id": "DE-amazon-SKU-001",
  "country": "DE",
  "platform": "amazon",
  "sku": "SKU-001",
  "url": "https://example.com/product-001",
  "page_type": "product_detail",
  "roi_profile": "amazon_product_detail_de",
  "enabled": true
}
```

字段约束：

- `country` 只能为 `DE` 或 `IT`。
- `platform` 为平台标识。
- `sku` 是内部商品标识。
- `url` 是该市场实际扫描地址。
- `page_type` 当前主要为 `product_detail`。
- `roi_profile` 指向平台和页面类型的 ROI 配置。
- `enabled=false` 的商品不参与扫描。

## 7. 真实截图和 ROI 规格

每次有效扫描至少需要：

1. 打开商品 URL。
2. 等待 DOM、商品区域和必要选择器。
3. 处理已配置的 Cookie 或继续访问弹窗。
4. 保存完整页面截图。
5. 根据 ROI 配置裁剪加入购物车区域。

ROI 是整张截图中交给 OCR 的矩形子区域，优先使用相对比例坐标，也可以使用稳定 CSS 选择器：

```json
{
  "id": "amazon_product_detail_de",
  "platform": "amazon",
  "page_type": "product_detail",
  "viewport": {"width": 1440, "height": 900},
  "region": {"left": 0.65, "top": 0.55, "right": 0.98, "bottom": 0.90},
  "selector": null,
  "enabled": true
}
```

异常扫描必须保存完整截图和 ROI 截图，以及商品、国家、URL、页面标题和时间。健康截图只保留到下一次健康扫描完成。

## 8. OCR 和词库规格

OCR 只在本地执行，只处理 ROI。真实扫描阶段首选 Tesseract，语言包为 `eng/deu/ita`；引擎通过适配器接入，后续可以替换为其他本地引擎。

至少支持：

| 语言 | 目标词汇示例 |
|---|---|
| 英文 | `Add to cart`、`Add to basket` |
| 德文 | `In den Warenkorb`、`In den Einkaufswagen`、`Zum Warenkorb` |
| 意大利文 | `Aggiungi al carrello`、`Aggiungi al cestino` |

匹配前必须：

- 转换大小写。
- 合并连续空格。
- 统一标点和连字符。
- 保留并兼容德文、意大利文重音字符。
- 支持配置 OCR 常见变体。

扫描结果保存 OCR 原文、归一化文本、匹配词、置信度和识别框信息。

## 9. 技术故障和重试

技术故障包括：

- 页面打不开。
- 页面加载超时。
- 必要商品选择器未出现。
- 截图失败。
- ROI 裁剪失败。
- OCR 引擎异常或超时。

同一扫描周期最多重试 2 次，使用退避等待。三次都失败后记录 `MONITORING_TECHNICAL_FAILURE`。技术故障不会创建库存风险告警，也不会关闭已有库存风险告警。

## 10. 图片和 Cookie 生命周期

### 10.1 图片

- 健康截图：下一次扫描完成后销毁上一张健康截图。
- 未处理异常：完整截图和 ROI 截图最多保留 3 天。
- 处理并复查恢复后：运营人员人工删除异常图片。
- 删除图片不删除必要的告警和扫描结构化记录。

### 10.2 Cookie

只保存 Cookie 名称、域名、路径、过期时间、是否存在和脱敏摘要或哈希值。完整 Cookie 值不得进入截图元数据、告警记录、日志或通知。

Cookie、语言、币种和配送信息只能作为辅助证据，国家归属以商品任务的 `country` 字段为准，不使用 IP 地理位置判断国家。

## 11. API 合同

MVP 和真实扫描阶段保留以下基础接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 返回本地监控页面 |
| GET | `/api/health` | 服务状态和运行模式 |
| GET | `/api/products` | 商品和当前状态 |
| GET | `/api/scans` | 扫描结果 |
| GET | `/api/alerts` | 告警列表 |
| POST | `/api/products/{product_id}/scan` | 执行一次扫描 |
| POST | `/api/alerts/{alert_id}/verify` | 标记处理并执行复查 |

MVP 演示接口：

```text
POST /api/products/{product_id}/demo-result
{"result":"healthy|inventory_risk|technical_failure"}
```

该接口只在 demo 配置保留，真实扫描生产路由不暴露。

关键响应约束：

- 未知商品和告警返回 `404`。
- 同一商品已有扫描或复查时返回 `409`。
- 成功响应包含商品状态、扫描结果和告警摘要。
- 健康检查 MVP 返回 `{"status":"ok","mode":"demo"}`。

## 12. 数据模型

### 12.1 扫描结果

```json
{
  "scan_id": "scan-2026-01-01T10:00:00Z",
  "task_id": "DE-amazon-SKU-001",
  "country": "DE",
  "sku": "SKU-001",
  "platform": "amazon",
  "started_at": "2026-01-01T10:00:00Z",
  "finished_at": "2026-01-01T10:00:08Z",
  "status": "healthy",
  "ocr_text": "In den Warenkorb",
  "matched_phrase": "In den Warenkorb",
  "ocr_confidence": 0.96,
  "full_screenshot_path": null,
  "roi_screenshot_path": null,
  "cookie_summary": [],
  "error": null
}
```

### 12.2 告警事件

```json
{
  "event_id": "event-0001",
  "type": "PRODUCT_ADD_TO_CART_MISSING",
  "status": "OPEN",
  "country": "DE",
  "platform": "amazon",
  "sku": "SKU-001",
  "first_seen_at": "2026-01-01T10:00:00Z",
  "last_seen_at": "2026-01-01T10:00:08Z",
  "failure_count": 1,
  "full_screenshot_path": "...",
  "roi_screenshot_path": "...",
  "ocr_text": "",
  "matched_phrase": null,
  "operator_note": null
}
```

MVP 内存模型可以使用现有 Python dataclass 和枚举；真实扫描阶段映射到 MySQL 的 `products`、`scan_runs`、`alerts`、`alert_transitions`、`artifacts`、`roi_profiles` 和 `phrase_sets` 表。

## 13. 架构边界

采用模块化单体：一个 Python 进程提供 HTTP、手动扫描和后续调度入口，模块通过接口协作。

### 13.1 领域层

只包含 `Product`、`Scan`、`Alert`、状态规则、告警去重和词匹配结果。不能导入 FastAPI、Playwright、SQLAlchemy、Tesseract、MySQL 或飞书 SDK。

### 13.2 应用层

包含 `ScanProduct`、`VerifyAlert`、列表查询和后续 `RunScheduledScan`，只依赖领域对象和端口接口。

### 13.3 适配器层

实现 `DemoScanner`、未来 `PlaywrightScanner`、`TesseractOcrAdapter`、内存仓储、MySQL 仓储、本地证据存储和未来通知适配器。

核心接口：

```python
class Scanner(Protocol):
    async def scan(self, target: ScanTarget) -> ScanObservation: ...

class OcrEngine(Protocol):
    async def recognize(self, image: ImageRegion) -> OcrResult: ...

class Notifier(Protocol):
    async def notify(self, event: AlertEvent) -> None: ...
```

应用层只接收 `ScanObservation` 和 `OcrResult`，不能依赖具体浏览器、OCR 或数据库类型。

## 14. 配置、运行和依赖

- Python 版本要求遵循 `pyproject.toml` 的 `requires-python`。
- 使用 `uv` 管理 Python 依赖和锁文件。
- MVP 启动：`uv run python app.py`。
- 当前环境如全局 uv 缓存不可写，使用项目内 `.uv-cache`：`$env:UV_CACHE_DIR="$PWD\.uv-cache"`。
- MVP 不需要 Kafka、MySQL、OCR 模型或外部 API Key。
- 真实扫描阶段新增依赖必须通过适配器和可选配置引入，不能让 MVP 启动依赖生产服务。

## 15. 测试和验收

### 15.1 MVP 验收

- 20 个商品，国家集合为 `DE`、`IT`。
- 新商品为 `not_scanned`。
- 扫描进入 `scanning`，完成后进入三种结果之一。
- 库存风险单次有效扫描即创建告警，重复扫描只累计失败次数。
- 技术故障不创建库存风险告警，不关闭已有告警。
- 健康复查进入 `resolved`，异常复查进入 `reopened`。
- 页面按钮不会重复提交，超时和错误后可以重试。
- 页面显示最近扫描时间、耗时和常见操作反馈。
- 运行完整 `unittest` 测试并完成本地浏览器 smoke。

### 15.2 真实扫描验收

- 能读取 DE/IT 静态商品清单并按小时运行。
- 能使用固定视口完成页面等待、弹窗处理、完整截图和 ROI 裁剪。
- OCR 只处理 ROI，能够匹配英、德、意加购词库。
- 有效扫描缺词创建库存风险，技术失败经过 2 次重试后记录技术故障。
- 持续异常不重复创建活动告警。
- 待验证商品强制重新截图和 OCR。
- 健康截图在下一次扫描完成后删除，异常图片按 3 天和人工删除规则处理。
- 持久化记录不包含完整 Cookie 值、密码或 API Key。

## 16. 与现有文档的关系

| 文档 | 作用 |
|---|---|
| `prd.md` | 完整业务目标和真实扫描范围 |
| `prd_mvp.md` | 当前 MVP 产品范围和演示验收 |
| `SPEC.md` | 合并后的阶段化系统规格，作为实现边界 |
| `docs/ARCHITECTURE.md` | 技术选型、模块边界和数据设计依据 |
| `TDD.md` | 测试驱动约束和状态边界 |
| `Tasks.md` | 从当前 MVP 继续开发的任务计划 |

当文档出现冲突时，当前实现必须先满足 `prd_mvp.md` 的 MVP 非目标；真实扫描任务只有在 MVP 验收完成后才执行。
