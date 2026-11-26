# 项目交接

## 接手基线

核对日期为 2026-11-25。项目位于 `D:\WZ_Project\ai-spider`，当前分支为 `master`，HEAD 为 `c25fda0`（开放 Amazon 九站并严格验证默认配送邮编），本地分支领先 `origin/master` 一个提交。此前 148 项测试的 Location 改动仍在当前模板中，当前 HEAD 另含九站和严格默认邮编更新。检查时仅 `AGENTS.md` 有已有跟踪改动，另有下文列出的六个未跟踪脚本。本次只新增交接文档。

需求以 [完整 PRD](../prd.md) 和 [MVP PRD](../prd_mvp.md) 为准。已有 [架构](ARCHITECTURE.md)、[SPEC](../SPEC.md)、[TDD](../TDD.md)、[任务](../Tasks.md)、[开发计划](superpowers/plans/) 和 [Live 运行手册](real-scan-runbook.md) 原样保留。若文档中的早期方案和当前实现不一致，以实际代码判断运行行为，以较新的确认需求判断下一步。

## 目标和架构

监控欧洲电商商品的加购入口，尽早发现潜在库存风险，并通过告警、人工处理、复查闭环。系统采用 Python + uv、FastAPI 和原生 HTML/JavaScript，部署为模块化单体。应用用例依赖仓储和扫描接口，Playwright Chromium、Tesseract、SQLAlchemy/MySQL 是适配器。证据图片留在本地，MySQL 保留状态和关联。网站交互只用于读取页面及设置配送；库存调整由业务人员处理。

启动入口是 [app.py](../app.py) 和 [bootstrap.py](../app/monitoring/bootstrap.py)。Windows 项目根目录运行 `uv run python app.py`，默认本机 8000。Live 需要 `MONITORING_MODE=real`、`MONITORING_INPUT_MODE=live`、可用的 Chromium/Tesseract 与指向 `cart_monitor` 的 `MONITORING_DATABASE_URL`。手动验收用 `MONITORING_SCHEDULER_ENABLED=false`，从 `/api/health` 核对模式及调度。另有 demo 内存模式及 real/manifest 截图输入模式；历史截图缺少 Live DOM 和实际配送证据。

## 已实现及验证边界

| 能力 | 当前实现及位置 | 验证范围 |
|---|---|---|
| 商品逐条录入和监控界面 | [API](../app/monitoring/api/routes.py)、[录入校验](../app/monitoring/config/catalog_schema.py)、[模板](../app/monitoring/templates/index.html)。支持平台、店铺、站点、ASIN、SKU、名称、URL、添加人；以平台、站点、店铺代码、SKU 联合去重，内部商品 ID 保持稳定。商品表为 SKU → Location → 商品名，含竖向列分隔，按店铺、站点、SKU、状态筛选；从商品进入其扫描历史。 | 代码和自动化已核对；本次未重新打开前端做视觉验收。 |
| Amazon 九站和配送 | [站点映射](../app/monitoring/config/markets.py)、[Amazon YAML](../app/platforms/ecommerce/amazon.yaml)、[PlaywrightScanner](../app/monitoring/adapters/playwright_scanner.py)。DE/IT/FR/ES/GB/SE/BE/PL/NL 由站点查默认邮编；历史 postal_code 和跳过标志不参与 Live 决策。缺邮编或实际读回不符即技术故障。入库平台选项不等于 Live 扫描支持，当前真实扫描仅 Amazon 九站。 | 九站配置和 NL 受控链路已验证；九站真实通过情况未验收。 |
| 商品证据及判定 | [扫描器](../app/monitoring/adapters/playwright_scanner.py)、[ROI](../app/monitoring/adapters/roi.py)、[OCR](../app/monitoring/adapters/ocr_tesseract.py)、[判定](../app/monitoring/application/real_observation.py)、[词库](../config/phrase_sets.json)。配送后重查页面就绪，空白全图或 ROI 补拍一次。健康要求可用 DOM 按钮和 ROI OCR 加购文案同时成立；库存风险要求有效证据、确认缺少可用按钮并明确识别不可购买文案。技术故障不生成库存告警，也不能作为恢复证据。 | 受控 Chromium/Tesseract NL 样例通过；不能据此认定 Amazon.nl 实际接受 1012。 |
| 截图、历史和数据库 | [本地证据](../app/monitoring/adapters/artifact_store_local.py)、[模型](../app/monitoring/adapters/mysql/models.py)、[仓储](../app/monitoring/adapters/mysql/repositories.py)、[截图 API](../app/monitoring/api/routes.py)。每次扫描关联自己的完整图和 ROI，历史通过 scan ID 图片 URL 读取，缺图允许空值。截图根目录限制挡住任意文件读取；本地路径只用于后端定位。001 初始迁移、002 商品录入迁移均在仓库。 | 自动化覆盖仓储和截图约束；仓储测试使用内存 SQLite，本次未查询当前 MySQL 迁移状态。此前 002 验证见 [CHANGELOG](../CHANGELOG.md)。 |
| 告警和处理 | [扫描用例](../app/monitoring/application/scan_product.py)、[复查](../app/monitoring/application/verify_alert.py)、[误报关闭](../app/monitoring/application/dismiss_alert.py)。活动告警去重，人工复查确认恢复后 RESOLVED；已确认误报走 DISMISSED 并保存流转历史，普通健康扫描不会直接关闭旧 OPEN 告警。 | 自动化通过。本次未读写历史告警。 |
| 定时执行 | [服务生命周期](../app/monitoring/entrypoints/service.py)、[批次](../app/monitoring/application/scheduled_scan.py)、[调度](../app/monitoring/entrypoints/hourly_scan.py)。支持开关、每小时配置、并发和超时。 | 自动化覆盖，真实持续调度待验收。手动验收仍保持关闭。 |

## 保留的六个未接入文件

| 文件 | 角色与接入状态 |
|---|---|
| [amazon_popups.py](../app/monitoring/adapters/amazon_popups.py) | 阶段与站点规则、控件筛选、有限动作及后置条件。当前扫描器未接入，当前 Amazon YAML 仍是旧选择器流程。 |
| [amazon_visit.py](../app/monitoring/adapters/amazon_visit.py) | 安全/无效页识别、ASIN 和邮编辅助函数。主流程未采用。 |
| [visit_diagnostics.py](../app/monitoring/adapters/visit_diagnostics.py) | 按扫描和尝试记录截图、脱敏 DOM、控件及导航信息。当前运行链路未调用。 |
| [scan_context.py](../app/monitoring/application/scan_context.py) | 扫描 ID 和尝试上下文。当前用例未接入。 |
| [test_amazon_popup_rules.py](../tests/test_amazon_popup_rules.py) | 未接入规则模块的独立测试。 |
| [test_amazon_visit.py](../tests/test_amazon_visit.py) | 独立辅助函数测试与依赖后续导航行为的回归用例。 |

保留文件不能视为运行功能。前次试验中的 GB Apply 阶段规则、统一弹窗链、BE ASIN 前置保护与重定向诊断没有随这六个文件接入当前版本。

## 实际测试与问题

- `.venv/Scripts/python.exe -m unittest discover -s tests` 运行 157 项，156 项通过、1 项错误。未跟踪的 `test_amazon_visit.NavigationTests.test_aborted_homepage_navigation_reopens_original_once` 期待导航中断后重开一次；当前跟踪版 `_reopen_product` 抛出 `net::ERR_ABORTED`。这是保留测试与当前主流程的行为差异。
- 使用相同发现入口，仅排除上述两个未跟踪测试模块，跟踪基线 150 项全部通过。套件包含受控 NL 邮编读回、完整截图、ROI 和 Tesseract 健康判定，以及 API、前端模板、证据路径、告警和仓储测试。
- 本轮未调用真实 Live 扫描、未查当前线上 MySQL、未启动调度。此前 Live 成功或受阻记录只作历史参考。
- 当前继续购物路径含基于旧选择器的点击。恢复 Live 验收前先检查该路径是否区分普通操作与实际指向验证端点的同名控件，并核对同站、原 ASIN、页面标题。不能因 URL 仍是原商品地址就断定已到正常详情页。
- 当前 GB 邮编匹配仍可能拒绝无空格的 `SW1A1AA`。BE 语言层及先前 ASIN 变化需重新取证，PL 双框和 NL 匿名配送需验证真实 DOM。旧版曾遇到 Amazon 安全验证及执行环境外网限制，应分别诊断。

## 下一阶段顺序及剩余量

1. **先补安全与身份校验（约 0.5–1 天）**。核对六个模块与当前端口和扫描错误码，补失败测试，把安全验证检查放在交互前后，确认按钮用途、同站、原 ASIN 与商品标题。对明确普通且可点击的交互，每个状态只处理有限次数，点击后验证结果。未知弹窗留证，避免点击用途不明的控件。解决导航中断测试与当前实现的差异。
2. **打通已取证的配送和证据缺口（约 1–2 天）**。优先 GB 邮编规范化及读回校验；再用 BE、PL、NL 的实际页面验证控件和跳转。复用现有 YAML 和扫描器，检查没有绕过邮编硬校验、证据空白保护或 DOM/OCR 双证据。网站取证受会话状态影响，等待时间不计入编码估算。
3. **本机回归及小批 Live 验收（约 0.5–1 天）**。每次代码修改运行相关测试并写一条中文 CHANGELOG；先请用户重启本机服务并确认进程版本，再扫健康和异常候选各一次，核对历史、截图和告警。受安全验证阻断时停止当前扫描并留证，继续其他获准样例。九站实测结果分别报告。
4. **验证自动定时扫描（约 0.5–1 天）**。完成手动闭环后，取得授权再进行受控调度验证。核对间隔、并发、超时、持久化与告警去重。外部通知、其他平台真实扫描及生产化的证据清理按完整 PRD 排后续，未纳入上面的工作量。

## 操作约束

- 不绕过验证码、机器人挑战、登录或访问限制；不自动点击加购、下单、支付，不自动改库存。不用受控样例冒充真实 Live。
- 诊断过滤 Cookie、Token、密码、表单敏感值和 URL 查询信息；数据库凭据从本机配置读取，不输出、不提交。保留历史商品 ID、扫描、截图和告警关联。
- 未经授权不执行 Alembic 迁移、删除或清空数据，也不使用 stamp 跳过迁移。可先核对目标库及版本，再决定下一步。保持 Scheduler 关闭，除非任务明确要求开启。
- 不自动暂存、提交、推送、切换分支或清理现有未提交文件；任务结束说明改动、测试和 Git 状态。代码修改按 [AGENTS.md](../AGENTS.md) 更新 [CHANGELOG](../CHANGELOG.md)。
