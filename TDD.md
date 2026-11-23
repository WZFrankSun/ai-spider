# 商品加购入口库存风险监控 MVP 测试驱动开发方案

## 1. 文档目的

本文档把 `prd_mvp.md` 转换为可执行的测试驱动开发约束。MVP 的目标是验证本地演示服务中的业务状态流转，不验证真实电商页面、真实 OCR 准确率或外部通知服务。

测试先于实现。每个新增行为都必须先写一个能够失败的测试，再实现最小代码使其通过，最后运行完整测试集确认没有回归。

## 2. 测试范围

### 2.1 MVP 必测范围

- 商品 fixture 包含德国和意大利合计 20 条记录。
- 商品初始状态为 `not_scanned`。
- 扫描执行期间状态为 `scanning`。
- 演示结果可以切换为 `healthy`、`inventory_risk` 或 `technical_failure`。
- 健康结果表示识别到加入购物车入口。
- 库存风险结果表示扫描有效但没有识别到加入购物车入口。
- 技术故障结果表示页面或识别流程不可判定。
- 技术故障不能创建库存风险告警。
- 技术故障不能自动关闭已有库存风险告警。
- 同一商品的持续库存异常复用一个告警并增加 `failure_count`。
- 库存异常经过健康复查后变为 `resolved`。
- 未知商品和未知告警返回 HTTP 404。
- 服务无需 OpenAI API Key、外网和 OCR 模型即可启动。

### 2.2 MVP 不测范围

- 真实 Amazon、Shopify 页面访问。
- Playwright 截图和页面等待的真实稳定性。
- 本地 OCR 引擎准确率和多语言模型效果。
- 每小时调度器的时间精度。
- Cookie 读取、脱敏和保存。
- 飞书 Webhook 投递。
- 数据库持久化、用户权限和多节点执行。

## 3. 测试层次

### 3.1 单元测试

单元测试针对演示扫描器、状态转换和告警去重。测试不依赖 FastAPI、浏览器或网络。

重点文件：

- `app/monitoring/adapters/demo_scanner.py`
- `app/monitoring/domain/models.py`
- `app/monitoring/domain/policies.py`
- `tests/test_monitoring_use_cases.py`

### 3.2 API 合约测试

使用 FastAPI 的 `TestClient` 测试 HTTP 状态码、JSON 字段和错误响应。每个测试创建独立的应用和内存仓储，避免测试之间共享内存状态。

重点文件：

- `app/monitoring/api/routes.py`
- `tests/test_monitoring_api.py`

### 3.3 页面冒烟测试

MVP 页面使用原生 HTML 和 JavaScript。页面冒烟测试先验证：

- `/` 返回 200。
- 页面包含商品表格、告警表格和演示结果切换控件。
- 页面调用的 API 路径与后端接口一致。

如果环境安装了 Playwright，再增加浏览器级测试，验证按钮点击后的状态刷新。Playwright 浏览器测试不是 MVP 单元测试的前置条件。

### 3.4 真实扫描集成测试（后续）

真实扫描接入时，必须在真实网络测试前提供假的浏览器页面和假的 OCR 适配器。集成测试应覆盖：

- 页面加载失败。
- 必要选择器缺失。
- 截图失败。
- ROI 裁剪失败。
- OCR 引擎异常。
- OCR 成功但没有匹配词汇。
- OCR 成功且匹配德文、意大利文或英文词汇。

真实站点测试只能作为手动验收，不得成为默认测试套件的一部分。

## 4. 状态模型测试

### 4.1 商品状态

| 状态 | 进入条件 | 离开条件 | 必测断言 |
|---|---|---|---|
| `not_scanned` | 商品刚创建 | 用户发起扫描 | 初始商品全部为此状态 |
| `scanning` | 扫描任务开始 | 扫描完成或失败 | 扫描期间禁止重复任务 |
| `healthy` | 有效扫描匹配加购词 | 下一次扫描改变结果 | 记录匹配词和置信度 |
| `inventory_risk` | 有效扫描没有匹配词 | 健康复查或再次异常 | 创建或更新库存告警 |
| `technical_failure` | 页面或识别环节失败 | 下一次有效扫描 | 不创建库存风险告警 |

### 4.2 告警状态

| 状态 | 允许的来源 | 必测断言 |
|---|---|---|
| `open` | 首次库存风险 | 创建一个告警 |
| `acknowledged` | 用户查看 | 只更新处理状态 |
| `pending_verification` | 用户标记已处理 | 下一次扫描强制执行 |
| `resolved` | 有效健康复查 | 只有健康结果才能进入 |
| `reopened` | 待验证后仍为库存风险 | 保留同一事件并更新次数 |

技术故障不会触发 `resolved`，也不会自动关闭已有库存风险事件。

## 5. 测试用例清单

### 5.1 商品和 fixture

- `test_demo_store_contains_twenty_products`
  - 断言商品数为 20。
  - 断言国家集合为 `DE` 和 `IT`。
  - 断言每个国家默认有 10 条记录。

- `test_products_start_as_not_scanned`
  - 创建新 store。
  - 断言每个商品的状态为 `not_scanned`。

### 5.2 演示结果切换

- `test_next_scan_can_be_set_to_healthy`
  - 将 `DE-001` 的下一次结果设为 `healthy`。
  - 扫描后断言商品状态为 `healthy`。
  - 断言 OCR 文本和匹配词存在。

- `test_next_scan_can_be_set_to_inventory_risk`
  - 将商品结果设为 `inventory_risk`。
  - 扫描后断言创建 `PRODUCT_ADD_TO_CART_MISSING`。

- `test_next_scan_can_be_set_to_technical_failure`
  - 将商品结果设为 `technical_failure`。
  - 扫描后断言商品进入技术故障状态。
  - 断言库存风险告警数量不增加。

### 5.3 扫描互斥

- `test_scan_marks_product_scanning_before_completion`
  - 使用可控的扫描执行器暂停完成步骤。
  - 断言商品在完成前为 `scanning`。

- `test_second_scan_is_rejected_while_first_scan_is_running`
  - 对同一商品并行发起两次扫描。
  - 断言第二次操作返回冲突或业务错误。
  - 断言只保留一个扫描结果。

### 5.4 告警去重与恢复

- `test_repeated_inventory_risk_updates_one_alert`
  - 连续扫描同一异常商品两次。
  - 断言告警数量仍为 1。
  - 断言 `failure_count` 为 2。

- `test_technical_failure_does_not_create_inventory_alert`
  - 设置下一次结果为技术故障。
  - 断言库存告警数量保持不变。
  - 断言技术故障记录包含错误原因。

- `test_technical_failure_does_not_resolve_inventory_alert`
  - 先创建库存风险告警。
  - 再设置一次技术故障并执行复查。
  - 断言原告警仍为 `open` 或 `pending_verification`。

- `test_healthy_verification_resolves_inventory_alert`
  - 先创建库存风险告警。
  - 标记待验证并返回健康结果。
  - 断言告警状态为 `resolved`。

- `test_failed_verification_reopens_inventory_alert`
  - 先创建库存风险告警。
  - 标记待验证并返回库存风险结果。
  - 断言仍使用原告警 ID，并进入 `reopened`。

### 5.5 API 合约

- `test_health_returns_demo_mode`
  - `GET /api/health` 返回 200。
  - JSON 为 `{"status":"ok","mode":"demo"}`。

- `test_products_returns_country_and_status_fields`
  - `GET /api/products` 返回 20 条记录。
  - 每条记录包含商品 ID、国家、SKU、平台和状态。

- `test_scan_endpoint_transitions_status`
  - `POST /api/products/{id}/scan` 返回扫描结果。
  - 返回状态与预期演示结果一致。

- `test_alert_verification_endpoint_resolves_or_reopens`
  - 验证接口根据下一次结果返回 `resolved` 或 `reopened`。

- `test_unknown_product_and_alert_return_404`
  - 未知商品扫描返回 404。
  - 未知告警验证返回 404。

## 6. 测试数据约束

- 测试不得依赖当前系统时间的具体值，只检查时间字段存在且前后顺序合理。
- 测试不得依赖外部 URL 返回内容。
- 每个测试创建新的 `DemoStore` 或新的应用实例。
- 演示结果切换必须可恢复，测试结束后不能污染其他测试。
- Cookie、API Key 和真实商品账号不得出现在 fixture 或测试输出中。

## 7. 命令

项目自带虚拟环境时运行：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

如果需要单独运行 MVP 测试：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_mvp_store tests.test_mvp_api -v
```

如果后续安装 pytest，可以增加：

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

## 8. 完成门槛

只有以下条件全部满足，才可以把 MVP 标记为可演示：

- 所有单元测试和 API 合约测试通过。
- 状态切换测试覆盖五种商品状态。
- 技术故障不会产生库存风险告警或自动关闭库存告警。
- 演示结果切换覆盖健康、库存风险和技术故障。
- 服务不依赖 OpenAI、外网和真实 OCR 模型启动。
- 本地页面能够完成一次异常到恢复的闭环。
- 测试输出不包含凭据、完整 Cookie 或真实账号信息。
