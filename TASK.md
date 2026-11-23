# 商品加购入口库存风险监控 MVP 任务清单

## 1. 目标

基于现有 Playwright 爬虫基础，完成一个不依赖外部网站的本地 MVP 演示。MVP 先验证商品扫描状态、库存风险告警、技术故障隔离和修复复查，不提前接入真实 OCR、定时调度或飞书。

需求来源：`prd_mvp.md`、`TDD.md`。

## 2. 现有基础

可复用模块：

- `app/browser/browser_manager.py`：浏览器和会话生命周期。
- `app/browser/browser_session.py`：页面、平台和会话变量。
- `app/platforms/registry.py`：平台 YAML 配置加载。
- `app/tools/browser/screenshot.py`：现有截图工具和页面就绪等待。
- `app/core/registry.py`：工具注册。
- `app/core/executor.py`：工具执行和错误封装。
- `app/workflows/crawl_list.py`：列表和详情页批量工作流。

演示能力收敛在 `app/monitoring` 模块内（`MonitoringContainer.demo()` 与 `create_demo_app()`），避免改变已有爬虫工具的公共行为。

## 3. 任务依赖图

```text
T0 环境与基线
  ↓
T1 状态模型与 fixture
  ↓
T2 确定性扫描与告警状态机
  ├──────────────┐
  ↓              ↓
T3 API 合约     T4 演示结果切换与扫描互斥
  └──────┬───────┘
         ↓
T5 演示页面
         ↓
T6 集成验证与交付检查
         ↓
T7 真实 Playwright/OCR 接入（后续，不属于 MVP）
```

## 4. 任务清单

### T0：建立环境和验证基线（已完成）

**目标**：确认项目可以使用 `.venv` 执行测试和 FastAPI 服务。

**检查项**：

- [x] 确认 Python 版本满足 `pyproject.toml` 的要求。
- [x] 确认 `.venv` 可导入 FastAPI、Uvicorn、Pydantic。
- [x] 运行现有 MVP 测试，记录基线结果。
- [x] 检查测试命令不依赖 OpenAI API Key 或外网。

**完成标准**：能够运行 `unittest`，失败时能区分环境缺失和业务失败。

### T1：实现商品和状态模型（已完成）

**目标**：统一商品、扫描结果、告警和状态枚举。

**建议文件**：

- `app/monitoring/domain/models.py`
- `app/monitoring/domain/policies.py`
- `tests/test_monitoring_use_cases.py`

**开发顺序**：

1. 先写商品数量、国家集合和初始 `not_scanned` 状态测试。
2. 再实现 `DemoProduct`、`ScanResult`、`AlertEvent` 和枚举。
3. 创建德国和意大利各 10 条 fixture。
4. 运行测试确认通过。

**完成标准**：商品数量为 20，国家为 `DE` 和 `IT`，新商品全部为 `not_scanned`。

### T2：实现确定性扫描和告警状态机（已完成）

**目标**：支持健康、库存风险和技术故障三种扫描结果，并隔离技术故障。

**建议文件**：

- `app/monitoring/application/scan_product.py`
- `app/monitoring/domain/policies.py`
- `tests/test_monitoring_use_cases.py`

**行为**：

- 扫描开始时商品变为 `scanning`。
- 健康结果变为 `healthy`，写入 OCR 文本和匹配词。
- 缺少加购词结果变为 `inventory_risk`，创建或更新库存告警。
- 技术故障变为 `technical_failure`，只记录技术故障。
- 技术故障不创建库存告警。
- 技术故障不关闭已有库存告警。
- 同一商品持续异常只保留一个未关闭告警。

**开发顺序**：

1. 为三种结果分别写失败测试。
2. 实现单次扫描。
3. 增加告警去重和失败次数累计。
4. 增加技术故障边界测试。

**完成标准**：TDD.md 中 T1、T2 相关测试全部通过。

### T3：实现 FastAPI API 合约（已完成）

**目标**：提供本地页面所需的稳定 HTTP 接口。

**建议文件**：

- `app/monitoring/api/routes.py`
- `app/monitoring/api/__init__.py`
- `app.py`
- `tests/test_monitoring_api.py`

**接口**：

| 方法 | 路径 | 结果 |
|---|---|---|
| GET | `/api/health` | 服务状态和 `demo` 模式 |
| GET | `/api/products` | 商品和状态列表 |
| GET | `/api/scans` | 最近扫描结果 |
| GET | `/api/alerts` | 告警事件列表 |
| POST | `/api/products/{product_id}/scan` | 执行单次演示扫描 |
| POST | `/api/alerts/{alert_id}/verify` | 标记待验证并执行复查 |

**开发顺序**：

1. 先写健康、商品、扫描、告警和 404 测试。
2. 实现 `create_app(store=None)`，每个测试可注入独立 store。
3. 将领域错误转换为 HTTP 404 或明确业务错误。
4. 使用 `app.py` 提供 Uvicorn 启动入口。

**完成标准**：API 合约测试全部通过，服务不读取 OpenAI 配置也能导入。

### T4：实现演示结果切换和扫描互斥（已完成）

**目标**：让演示覆盖完整状态流转，同时防止重复点击。

**建议文件**：

- `app/monitoring/application/scan_product.py`
- `app/monitoring/application/verify_alert.py`
- `tests/test_monitoring_use_cases.py`
- `tests/test_monitoring_api.py`

**行为**：

- 为商品设置下一次演示结果：`healthy`、`inventory_risk`、`technical_failure`。
- 扫描前为 `not_scanned` 的商品也支持切换结果。
- 扫描执行期间为 `scanning`。
- 同一商品已有运行中的扫描时，第二次扫描返回冲突或业务错误。
- `technical_failure` 不改变库存告警的关闭状态。
- 只有有效健康复查才允许进入 `resolved`。

**建议接口**：

```text
POST /api/products/{product_id}/demo-result
{
  "result": "healthy"
}
```

如果实现阶段发现不需要独立接口，也可以把结果设置合并到扫描请求，但必须保留可测试的领域方法。

**完成标准**：页面或 API 可以切换三种演示结果，测试覆盖技术故障隔离和并发扫描保护。

### T5：实现本地演示页面（已完成）

**目标**：运营人员无需调用命令行即可演示异常发现和修复验证。

**建议文件**：

- `app/monitoring/templates/index.html`

**页面内容**：

- 商品总数、德国数、意大利数和当前未恢复告警数。
- 商品列表，显示国家、SKU、平台、状态和立即扫描按钮。
- 告警列表，显示类型、国家、SKU、状态和失败次数。
- 演示结果选择器，支持健康、库存异常和技术故障。
- 扫描期间禁用当前商品按钮并显示 `scanning`。
- 首次扫描前显示 `not_scanned`。
- 技术故障显示错误原因。
- 处理并验证按钮触发复查。

**开发顺序**：

1. 先完成静态结构和可读状态样式。
2. 接入商品、扫描、告警和验证 API。
3. 增加结果切换和错误提示。
4. 使用浏览器手动完成一次异常到恢复流程。

**完成标准**：页面能够完成一条商品从未扫描、异常到恢复的演示流程。

### T6：集成验证与交付检查（已完成）

**目标**：确认 MVP 可本地运行，并且文档中的验收标准可以复现。

**检查项**：

- [x] 运行完整 `unittest` 测试。
- [x] 启动 `python app.py`。
- [x] 请求 `/api/health`。
- [x] 打开首页并确认 20 个商品显示。
- [x] 将一个商品切换为 `inventory_risk` 并扫描。
- [x] 确认告警创建且重复扫描不会重复创建告警。
- [x] 将告警商品切换为 `healthy` 并执行验证。
- [x] 确认告警变为 `resolved`。
- [x] 将商品切换为 `technical_failure`，确认不会关闭库存告警。
- [x] 检查输出没有 API Key、完整 Cookie 或真实账号信息。

**完成标准**：测试通过，服务可以启动，浏览器页面可完成演示闭环。

### T7：真实扫描接入（后续任务，不属于 MVP）

**目标**：把确定性演示替换为真实商品页面扫描。

**依赖**：T1 至 T6 全部完成并通过验收。

**后续拆分**：

1. 从 JSON/CSV 读取国家商品清单。
2. 复用 `BrowserManager` 和 `BrowserSession` 打开商品 URL。
3. 复用现有截图工具完成页面就绪等待和完整截图。
4. 增加平台与页面类型 ROI 配置。
5. 接入本地 OCR 适配器。
6. 增加英文、德文和意大利文词库及文本归一化。
7. 增加技术失败重试和扫描周期调度。
8. 增加健康截图清理、异常图片保留和 Cookie 脱敏摘要。
9. 最后接入飞书 Webhook。

## 5. 任务优先级

| 优先级 | 任务 | 原因 |
|---|---|---|
| P0 | T0、T1、T2、T3 | 形成可调用的领域和 API 闭环 |
| P0 | T4 | 覆盖状态切换和技术故障边界 |
| P1 | T5 | 形成面向运营的本地演示 |
| P1 | T6 | 验证可启动、可复现和可交付 |
| P2 | T7 | 真实浏览器和 OCR 接入，超出当前 MVP |

## 6. 任务完成定义

MVP 只有在以下条件都满足时才算完成：

- 领域状态和告警规则有自动化测试。
- API 错误和状态转换有自动化测试。
- 演示结果切换覆盖三种结果。
- `technical_failure` 不会生成库存风险告警或自动关闭库存告警。
- 页面防止扫描期间重复点击。
- 本地服务不依赖 OpenAI、外网或 OCR 模型即可启动。
- 页面可以展示并完成异常到恢复的闭环。
- 所有测试和手动验收结果都记录在交付说明中。
