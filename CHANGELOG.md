# 修改记录

每次任务记一条，写明日期、目的、涉及文件、具体变化和测试结果。

- 2026-11-23｜退役旧 Agent 框架和纯视觉方案｜涉及 `app/core/`、`app/tools/`、`app/agents/`、`app/workflows/`、`app/bootstrap.py`、`app/config.py`、`app/platforms/social/`、`examples/`、`.cursor/skills/amazon-screenshot/`（均删除），以及 `app/browser/browser_session.py`、`app/platforms/registry.py`、`pyproject.toml`、`uv.lock`、`.env`、`.env.example`、`.gitignore`、`prd.md`、`SPEC.md`、`TASK.md`、`Tasks.md`、`docs/real-scan-runbook.md`｜加购入口判定统一为 DOM 按钮可用性检查加 Tesseract ROI OCR，弃用多模态 LLM 看图方案；删除工具注册执行框架、LLM 选择器解析、examples 演示脚本和对应 Skill，清理 openai、loguru、pydantic-settings 依赖及 LLM 环境变量；`httpx2` 原本由 openai 间接引入，删除后改由 dev 依赖组显式声明，避免 FastAPI TestClient 失效｜135 个测试通过；Amazon Live 验收：`DE-amazon-001` 为 `healthy`（OCR 命中「In den Einkaufswagen」），`DE-amazon-negative-001` 为 `inventory_risk`（OCR 命中「Derzeit nicht verfügbar」）且告警 `alert-DE-amazon-negative-001` 保持单条累计，定时扫描全程关闭。

- 2026-11-23｜清理 MVP 死代码和空目录｜涉及 `app/mvp/`（删除）、`app/monitoring/api/routes.py`、`app/monitoring/api/__init__.py`、`app/monitoring/templates/`、`app/tools/extract/dom_snapshot.py`（删除）、`app/config`、`app/tools/network`、`app/workflow`（空目录删除）、`tests/`、`pyproject.toml`、`TDD.md`、`TASK.md`、`Tasks.md`、`docs/ARCHITECTURE.md`｜删除独立 `app/mvp` 模块，演示能力收敛到 monitoring 内的 `create_demo_app()`，`legacy_auto_recover` 更名 `demo_auto_recover` 并在模块内实现，页面模板移入 `app/monitoring/templates/`；135 个测试通过；Amazon Live 验收：`DE-amazon-001` 为 `healthy`（OCR 命中"In den Einkaufswagen"），`DE-amazon-negative-001` 为 `inventory_risk`（OCR 命中"Derzeit nicht verfügbar"）且告警 `alert-DE-amazon-negative-001` 保持单条累计，定时扫描全程关闭。

- 2026-11-23｜执行四个 Amazon 站点 Live 验收｜涉及商品目录、目录校验、ROI 和加购词库｜加入英国站和跨站候选；德国、意大利、法国、英国各验证 3 个健康和 3 个无加购案例，技术失败单列；142 个测试通过。

- 2026-11-23｜修复跨站点继续购物提示｜涉及 Amazon 平台配置、扫描器及测试｜补充意大利语变体和法语候选，重新打开商品链接后再检查提示｜142 个测试通过；健康与异常样例均尝试新版 Live，但浏览器访问 Amazon 被拒绝。

- 2026-11-23｜简化 Live 监控面板｜涉及 FastAPI 页面渲染、引导配置、前端模板和页面测试｜隔离演示控件、改用 SKU 或 ASIN 展示、区分活动和关闭告警、优化表格层级｜141 个测试通过，Chromium 验证跨站点历史、关闭告警及三种窗口宽度。

- 2026-11-23｜完善缺少加购入口告警判定｜涉及扫描判定、词库加载、词库配置和测试｜确认无可用 DOM 按钮直接判风险；仅用截图时要求命中多语言不可购买文案且无加购文字，保留冲突与技术诊断｜140 个测试通过，未使用新版重跑 Amazon Live。

- 2026-11-23｜新增两款德国 Amazon Live 验收商品｜涉及 `config/products.real.json`｜新增 Razer Blade 16 和 MSI RTX 4080 SUPRIM X，复用购买区 ROI｜两次真实扫描均为库存风险，保存截图和记录，各生成一条活动告警。

- 2026-11-23｜修复多报价商品的 OCR 取图｜涉及扫描判定、Playwright ROI 和测试｜限定真实按钮控件，并直接截取通过可用性检查的同一候选；无法取到按钮小图时使用购买区｜138 个测试通过，Chromium 验证重复控件，历史真实截图通过按钮小图复现并识别；未复测新版 Live。

- 2026-11-23｜修复多报价商品的加购按钮检测｜涉及 Live 观察判定、Playwright ROI 和测试｜逐个核对同 ID 的按钮候选，跳过隐藏或禁用副本，优先裁剪可见启用按钮｜137 个测试通过，Chromium 重复按钮与 ROI 验证通过；尚未使用新版复测真实 Amazon。

- 2026-11-23｜优先依据可用的加购按钮判断 Live 扫描｜涉及观察判定、Playwright ROI、ROI 配置、监控面板和测试｜以无实际点击的 Playwright 检查确认按钮可用性，OCR 异常保留诊断，优先裁剪按钮并回退至购买区｜136 个测试通过，Chromium 遮挡与 ROI 验证通过；尚未复测真实 Amazon。

- 2026-11-23｜修复 Amazon 提示延迟与首页跳转竞争｜涉及 Live 扫描器、Amazon 平台配置及扫描器测试｜在页面就绪前后短暂等待 Cookie 拒绝按钮，补充多语言选择器，仅在同站首页导航冲突时补试一次｜133 个测试通过，Chromium 延迟弹窗验证通过；在已运行服务的真实截图看到了商品详情，新版尚未完成 Amazon Live 验证。

- 2026-11-23｜处理 Amazon Cookie 面板和首页跳转｜涉及 Playwright 扫描器及扫描器测试｜复用拒绝 Cookie 选择器，等待面板消失；若落在同站首页则重新打开商品链接一次，异常时保留诊断截图｜131 个测试通过，未执行真实 Amazon 复测。

- 2026-11-23｜处理 Amazon 继续购物提示页｜涉及 Playwright 扫描器、Amazon 平台配置和扫描器测试｜在校验商品标题前识别并点击一次可见的继续购物按钮，点击失败保留诊断截图｜130 个测试通过，未执行真实 Amazon 复测。

- 2026-11-23｜新增 9 条 Amazon 监控链接｜涉及商品目录、ROI 和加购词库配置、目录校验、前端和目录测试｜新增德/意/法商品，法国可在首页筛选，意法使用购买区 ROI 与本地词库｜128 个测试通过；本机 Live 逐条扫描均保存商品标题缺失的技术故障及诊断截图。

- 2026-11-23｜缩短页面就绪检查并按 SKU 查看历史｜涉及 Playwright 扫描器、重试策略、扫描用例、监控面板及测试｜就绪选择器最多等待 10 秒，缺失时保留诊断截图并结束该次扫描；扫描记录计入重试耗时；首页展示最新结果，按 SKU 展开历史｜128 个测试通过，前端脚本语法及历史过滤排序验证通过，未执行真实 Amazon 复测。

- 2026-11-23｜修复真实样例扫描超时与证据显示｜涉及 Live 扫描器、扫描与复查用例、商品 API、监控面板、商品与 ROI 配置及测试｜暂时停用配送邮编检查，延长扫描请求等待时间并恢复遗留的扫描状态，负向样例改用购买区截图，商品列表按开始时间展示最新扫描｜127 个测试通过，JavaScript 语法及最新记录选择验证通过，未执行 Amazon Live 复测。

- 2026-11-23｜减少误提交本地文件｜涉及 `.gitignore`、`CHANGELOG.md`｜忽略本地环境、扫描产物、安装文件、截图清单和助手工作记录｜仅检查 Git 忽略规则，未运行代码测试。

- 2026-11-23｜建立代码修改记录机制｜涉及 `AGENTS.md`、`CHANGELOG.md`、`.gitignore`｜补充 Git 汇报与操作规则，建立中文修改记录，完善本地缓存和敏感配置的忽略规则｜未运行代码测试，仅检查 Git 状态和忽略规则。
