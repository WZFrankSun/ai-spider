# Live 监控面板实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Live 面板只呈现真实监控所需的操作，以 SKU 或 ASIN 查找商品，并清晰展示扫描与告警。

**Architecture:** 保留 FastAPI、共享 HTML 模板和现有扫描接口，根据服务端运行模式渲染演示控件。展示标识独立于持久化主键，现有历史、证据和告警继续用内部 ID 关联。

**Tech Stack:** FastAPI、HTML/CSS、原生 JavaScript、unittest。

**Spec:** 本文件的「设计与范围」，业务基线为 `prd.md` 和 `SPEC.md`。

## Global Constraints

- Live 或真实截图输入页面隐藏演示控件。Demo 保留独立的运行模式和确定性验收能力。
- 保留扫描、OCR、ROI、截图、安全访问、复查和误报关闭的现有业务逻辑。
- SKU 和 ASIN 仅用于展示。使用国家、平台和内部 ID 区分跨市场记录。
- 既有数据库主键、数据和迁移保持原样。本次执行计划不包含提交或推送，只有得到明确授权后才能操作 Git 提交。

## 设计与范围

- 商品和告警统一显示商品名称及标识。真实 SKU 优先，`TEMP-ASIN-xxxxxxxxxx` 显示为 `ASIN xxxxxxxxxx`。普通 SKU 原样显示。历史窗口仍跟随所选商品和站点。
- 首页保留每个站点商品的最新扫描。告警默认展示活动事件，已恢复和已确认误报的事件可切换查看。Demo 使用内存仓储，Live 使用配置的仓储。对于数据库中的来源不明记录，先核实来源，以免把真实告警当成演示事件处理。
- 首页移除「前置条件」计数和静态流程条。保留运行模式与实际操作失败提示，原有启动检查和状态 API 继续服务诊断。
- 主背景 `#EEF3F6`，表面 `#FFFFFF`，奇偶行底色 `#F2F7FA`，表头 `#17364D`，正文 `#152C3D`，操作色 `#146B73`。状态继续用文字和色彩共同表达。
- 字体用 Microsoft YaHei UI 与 Segoe UI，标识、时间和耗时使用等宽数字。商品和证据左对齐，耗时和失败次数右对齐。
- 深色表头加列间细线，数据行交替底色，悬停和键盘聚焦有清晰反馈。手机宽度下仅表格容器可横向滚动。

```text
商品加购监控                    Live · 定时扫描关闭
商品扫描                         国家 [全部] 状态 [全部]
国家 | 商品 / SKU 或 ASIN | 状态 | 最近扫描 | 证据 | 操作
告警事件                         活动 [默认]  已关闭
商品 / SKU 或 ASIN | 状态 | 失败次数 | 操作
扫描历史                         选中商品后展开
```

页面的主要浏览顺序是商品、异常、证据。商品身份和扫描状态放在相邻列，方便运营逐行对照截图，减少首页占位说明。

## Review Focus

- Live 状态响应慢时，首次显示也没有「演示结果」表头或按钮。任务 1。
- 同 ASIN 同时出现在德国和意大利时，历史和扫描操作仍按所选站点区分。任务 2。
- 商品已移出启用目录时，历史告警仍可识别，允许使用内部 ID 作为最后的显示回退。任务 2。
- 已确认误报的事件仍可查询，活动数量和复查按钮不把它当作活动事件。任务 3。
- 长 SKU、错误码和窄屏会撑开表格，页面本身保持可滚动并且操作可用。任务 3。

### 任务 1 / 按模式隔离演示入口

**文件**：`app/monitoring/api/routes.py`、`app/monitoring/bootstrap.py`、`app/mvp/templates/index.html`、`tests/test_mvp_page.py`。

**接口**：保留 `GET /` 和 `POST /api/products/{product_id}/demo-result`。页面使用已有的 `MonitoringContainer.mode`。引导函数把已加载的 `MonitoringRuntimeConfig` 传给路由，修复页面可能读到默认输入模式的问题。

- [ ] 编写双模式页面测试。Demo 有「演示结果」表头和设置入口，Real HTML 里无演示控件，也无「前置条件」。Real 调用演示写接口返回 404。
- [ ] 运行 `python -m unittest discover -s tests -p test_mvp_page.py`，确认 Real 页面测试先失败。
- [ ] 用模板里的显式插槽按模式输出 Demo 表头和单元格。Real 仍复用商品表、扫描、历史以及复查。删除前置条件计数和静态流程条对应的 HTML、JS 和专用样式。
- [ ] 重新运行同一命令，确认通过。检查两个模式下表头和单元格数量一致。

### 任务 2 / SKU 或 ASIN 展示，延续内部关联

**文件**：`app/mvp/templates/index.html`、`tests/test_mvp_page.py`。

**接口**：在共享模板中加入 `productLabel(product)`，由 `sku` 和 `country` 形成可见标识。继续用 `product.id` 查找历史和提交扫描，告警用 `product_id` 查找显示标识。

- [ ] 添加浏览器脚本断言。真实 SKU 原样显示，`TEMP-ASIN-B0DTYXQWXM` 显示为 `ASIN B0DTYXQWXM`。德国和意大利的同 ASIN 历史互不混入。找不到商品对象的告警仍可展示。
- [ ] 实现标识格式化并用于商品表、历史标题、扫描提示及告警商品列。匹配临时前缀时仅接受符合 Amazon ASIN 格式的十位字母数字。
- [ ] 用浏览器或 Node 验证两条同 ASIN 的跨国操作各自使用正确的扫描 API，旧截图 URL 仍可打开。

### 任务 3 / 告警页简化与表格层级

**文件**：`app/mvp/templates/index.html`、`tests/test_mvp_page.py`、`CHANGELOG.md`。

**接口**：现有 `GET /api/alerts` 保留完整记录。面板默认呈现 `open`、`acknowledged`、`pending_verification`、`reopened`，并可切换查看 `resolved` 和 `dismissed`。

- [ ] 验证混合状态的告警数据只把活动事件纳入首页计数。切换可见已关闭事件，关闭事件没有复查按钮。
- [ ] 为商品、告警和历史表统一应用设计中的表头分隔、交替背景、数字对齐和滚动容器。将表头与实际数据列按同一顺序排列。
- [ ] 用 Chromium 在 1440px、768px 和 390px 查看页面。检查长标识、长错误码、窄屏滚动和键盘焦点。验证扫描按钮锁、按 SKU 查看历史、截图打开和告警复查仍可用。
- [ ] 运行 `python -m unittest discover -s tests`，记录结果。实现后在 `CHANGELOG.md` 写一条变更记录，汇报本次文件行号和 Git 差异。

## 内部 ID 迁移

本轮从日常界面移除 `DE-amazon-003` 这类编号。若后续需要连 API 与数据库也改用新主键，单独制定迁移。主键应包含市场、平台及 SKU 或 ASIN，先核对扫描、告警、证据记录和旧链接，再准备映射、备份、回滚与数据核对。只有明确授权后才执行。
