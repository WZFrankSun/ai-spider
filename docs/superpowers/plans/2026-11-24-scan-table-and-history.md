# 扫描列表与历史表格实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 说明逐商品记录的扫描资格，在主表展示配送 Location，并让历史表在较宽的页面中提供完整、易读的扫描证据。

**Architecture:** 主表和历史共用商品字段和证据渲染，历史始终按内部商品 ID 关联。配送目标沿用扫描器现有邮编优先级，扫描资格沿用现有市场规则。

**Tech Stack:** FastAPI、原生 HTML/CSS/JS、unittest、Playwright Chromium。

**Spec:** 本文件的「验收规则」，以及 [商品逐条录入设计](../specs/2026-11-24-product-entry-design.md)。

## Global Constraints

- 保留现有商品、历史、截图和告警关联。无需数据库迁移，不改变扫描或告警判定。
- Amazon Live 扫描保留 DE、IT、FR、GB 四站点；ES 测试记录仍可查看。
- 修改后同步 CHANGELOG。新版 Live 验收前提醒用户重启服务，确认后各跑一次预期健康和异常的样例。定时扫描保持关闭，不暂存、提交或推送。

## 验收规则

- 同一 ASIN 可以有不同站点记录。B07Q3DYMRD 的 DE、IT 行可扫描，ES 验证记录不可扫描，并说明具体原因。
- 商品扫描增加「Location（目标配送邮编）」列。优先显示用户自定义邮编，其次显示扫描器实际采用的站点或同站平台默认值。目标值只表达计划填写的邮编；没有已保存的实际读回值时，页面不将目标标记为已生效。暂未支持扫描的记录仍可展示其配置邮编。
- 历史显示平台、店铺码、站点、ASIN、SKU、商品名、URL、历史状态、扫描时间，以及与主表一致的证据。OCR 原文和匹配词位于同一单元格。错误通过状态旁的详情查看，整页和 ROI 截图统一用中文链接，缺图显示占位。
- 历史商品列使用当前商品资料，扫描状态、时间、错误和截图使用该次扫描自身数据。按内部 ID 隔离站点及店铺。当前资料不作为扫描时点的商品快照。
- 桌面工作区利用可用宽度。店铺码、站点、ASIN、SKU、扫描时间、状态及操作保持单行。长商品名和错误详情允许适度换行；URL 使用「打开商品页」。窄屏只在表格容器内横向滚动。

## Review Focus

- 同 ASIN 跨站点时，扫描资格和历史不会串行。任务 1、2。
- 用户邮编有前导零或空格时原样显示，默认值与扫描器一致。任务 1。
- 历史记录缺少截图或只有技术错误时仍可阅读，不显示失效图片。任务 2。
- OCR 长原文不挤压 ASIN 和 SKU 列，原文仍可按需展开。任务 2、3。
- 1440px、1920px 和 390px 下均能打开扫描操作，窄屏不产生整页横向滚动。任务 3。

### 任务 1 / 解释扫描资格并展示 Location

**Files:** `app/monitoring/api/routes.py`、`app/monitoring/adapters/playwright_scanner.py`、`app/monitoring/config/markets.py`、`app/monitoring/templates/index.html`、`tests/test_product_entry.py`。

**Interfaces:** 商品响应新增 `target_postal_code` 和 `scan_unavailable_reason`，保留原 `postal_code` 与 `can_scan`。

- [ ] 增加 API 测试：同 ASIN 的 DE、IT 可扫描，ES 显示原因；验证 `00174` 前导零、`SW1A 1AA` 空格及用户自定义邮编优先。
- [ ] 提取可由扫描器与列表复用的邮编解析规则，保持商品自定义、站点默认、平台同站配置的优先顺序。前端展示 Location 和不可用原因。
- [ ] 运行 `python -m unittest discover -s tests -p test_product_entry.py` 及扫描器相关用例。

### 任务 2 / 完善历史字段并统一证据

**Files:** `app/monitoring/templates/index.html`、`tests/test_monitoring_page.py`。

**Interfaces:** 复用 `GET /api/products` 和 `GET /api/scans`，使用 `product.id === scan.product_id` 关联。主表与历史调用同一证据渲染逻辑。

- [ ] 用同 ASIN 跨站点和跨店铺数据断言历史只显示所选 ID。测试旧记录无截图、技术故障和长 OCR 场景。
- [ ] 替换历史表头、空态跨列和数据渲染。OCR 同列展示匹配词并支持展开原文；错误提示和整页／ROI 链接与主表一致，继续使用已有截图 API。
- [ ] 使用浏览器验证切换商品后证据仍对应各自扫描。

### 任务 3 / 放宽布局并回归

**Files:** `app/monitoring/templates/index.html`、`tests/test_monitoring_page.py`、`CHANGELOG.md`。

- [ ] 放宽桌面工作区至 1920px，保留边距，给标识列设合理最小宽度和单行规则。长内容保留可读的换行或展开。
- [ ] 用 Chromium 在 1920px、1440px 和 390px 验证列对齐、长数据、滚动、筛选、截图和错误提示。
- [ ] 运行完整 unittest 和 `git diff --check`。用户确认重启后用新版跑健康及异常 Live 各一次，将实际结果记入 CHANGELOG。
