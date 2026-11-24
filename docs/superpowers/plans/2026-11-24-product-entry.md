# 商品逐条录入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 运营能逐条保存商品，在同页切换到扫描列表并按店铺、站点和 SKU 查找商品。

**Architecture:** 沿用 FastAPI、现有商品仓储和共享页面。MySQL 保证店铺维度去重，应用层统一判断商品能否发起真实扫描。

**Tech Stack:** Python、FastAPI、SQLAlchemy、Alembic、MySQL、原生 HTML/CSS/JS、unittest。

**Spec:** [已确认的商品逐条录入设计](../specs/2026-11-24-product-entry-design.md)。

## Global Constraints

- 平台为 Amazon、TikTok、Temu、eBay、SHEIN。站点为 DE、IT、FR、ES、GB、SE、BE、PL。
- 首版仅 Amazon DE、IT、FR、GB 可发起 Live；保存不触发扫描或告警。
- 序号在页面生成，保持已有产品主键、扫描和告警关联。
- 添加人从 Frank、Lvy、Nova、Drake 选择。默认店铺代码 H1-A1、H2-A1、H4-A1。
- 未经授权不迁移当前数据库、不删除数据、不暂存、提交或推送。

## Review Focus

- 并发提交同一商品只保存一条，另一条返回 409。任务 1、2。
- 跨店同 SKU 能各自保存，已有目录重启同步不覆盖运营资料。任务 1。
- 邮编前导零和空格能从 MySQL 原样读回。任务 1。
- 非支持商品即使直调手动或复查 API 也不创建扫描，定时入口跳过。任务 3。
- 窄屏、键盘及触屏均能查看错误详情，筛选不会混用同 SKU 的历史。任务 4。

### 任务 1 / 存储、去重和旧目录兼容

**文件**：`app/monitoring/domain/models.py`、`app/monitoring/application/ports.py`、`app/monitoring/adapters/mysql/models.py`、`repositories.py`、内存商品仓储、`app/monitoring/entrypoints/service.py`、`migrations/versions/002_product_entry_fields.py`、`tests/integration/test_mysql_repositories.py`。

**接口**：`Product` 新增 `store_code`、`asin`、`added_by`，并持久化已有 `postal_code`。商品仓储增加 `create(product: Product) -> None`，重复抛 `DuplicateProductError`。原 `save` 继续更新状态。

- [ ] 增加回归测试，验证相同 SKU 可在 IT 的 H1-A1、H4-A1 分别创建；同店同站重复被拒绝；`00174` 和 `SW1A 1AA` 读回一致；启动同步保留旧记录的自定义字段。
- [ ] 运行 `python -m unittest discover -s tests -p test_mysql_repositories.py`，确认新增测试先失败。
- [ ] 新迁移给现有资料列提供兼容的空值表示，保留 ID，把唯一约束替换为 `country, platform, store_code, sku`。旧店铺代码用空字符串，便于约束正常生效。回滚前检查跨店重复 SKU；有冲突明确停止，保留数据。
- [ ] 实现仓储新增及映射，数据库唯一约束负责并发防重，其他数据库异常原样处理。目录同步只补充缺失商品，已有记录保留运营资料和状态。
- [ ] 重跑仓储测试；生成离线迁移 SQL 并检查列和唯一约束。获授权后才在本机目标库执行迁移。

### 任务 2 / 新增商品 API

**文件**：`app/monitoring/api/routes.py`、`app/monitoring/config/catalog_schema.py` 或同目录的录入 schema、`tests/test_monitoring_api.py`。

**接口**：`POST /api/products` 接收 `platform, store_code, country, asin, sku, name, url, postal_code, added_by`，创建返回 201 和商品详情，重复返回 409，输入校验失败返回 422。`GET /api/products` 保留原字段并附带录入字段。

- [ ] 编写接口测试，覆盖 Amazon 从链接提取 ASIN、站点不符、非 HTTPS、ASIN 不符、非 Amazon ASIN 可空、重复请求与保存不发起扫描。
- [ ] 运行 `python -m unittest discover -s tests -p test_monitoring_api.py`，确认新增测试先失败。
- [ ] 实现枚举和必填校验，校验允许的站点域名及商品链接，保留 Amazon 变体参数；对新记录生成独立内部 ID。默认邮编复用按站点配置的字符串，显式填写优先。
- [ ] 重跑接口测试。检查响应包含新字段，旧 ID 和已有扫描链接不变。

### 任务 3 / 统一扫描资格

**文件**：`app/monitoring/domain/policies.py`、`app/monitoring/application/scan_product.py`、`verify_alert.py`、`scheduled_scan.py`、`app/monitoring/api/routes.py`、`tests/test_monitoring_api.py`、`tests/test_scheduled_scan.py`。

**接口**：`supports_live_scan(product: Product) -> bool` 仅允许 Amazon DE、IT、FR、GB。商品响应暴露 `can_scan: bool`，Demo 的原模拟动作照常可用。

- [ ] 验证真实模式下 Temu DE、Amazon ES 的手动和复查返回 409，定时扫描跳过，扫描记录和告警状态不变。Amazon IT 可以走现有扫描。
- [ ] 在进入真实扫描或修改复查状态前调用同一资格规则，并让列表的按钮使用服务端结果。
- [ ] 运行相关接口、定时扫描和复查测试，检查无副作用及旧场景回归。

### 任务 4 / 同页标签、商品表与回归

**文件**：`app/monitoring/templates/index.html`、页面测试、`CHANGELOG.md`。

- [ ] 增加录入与扫描标签。提交使用任务 2 的 API，显示逐字段错误和重复提示；成功后提供「查看商品」并定位新记录。
- [ ] 商品表显示设计稿全部字段，序号由过滤后的显示顺序计算。保留扫描锁、历史和截图链接；店铺、站点、SKU 联合筛选。技术故障提示支持悬停、聚焦及点击。
- [ ] 用 Chromium 验证键盘切换、窄屏滚动、保存后刷新、自定义邮编、跨店历史和禁用扫描动作。使用测试数据验证界面，区分真实 Live 结果。
- [ ] 运行 `python -m unittest discover -s tests`。当可使用已迁移的新版服务时，分别跑一次预期健康和无加购入口的 Amazon 案例，记录截图、OCR、实际状态与告警。保持定时扫描关闭。
- [ ] 在 `CHANGELOG.md` 写一条中文记录。汇报文件、行号、测试和 Git 摘要。
