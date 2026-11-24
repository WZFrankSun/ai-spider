# Live 截图与加购判定修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除配送切换期间的空白截图及错误健康结果，并验证用户从页面录入的自定义邮编能在 Amazon 页面生效。

**Architecture:** 保留 Playwright、Tesseract、现有商品仓储和扫描证据 API。扫描器先确认配送更新后的商品页，再获取同一轮 DOM 和图像证据；判定层使用 DOM 和 OCR 双证据决定是否健康。

**Tech Stack:** Python、Playwright Chromium、Pillow、Tesseract、FastAPI、MySQL、unittest。

**Spec:** 本文件「验收规则」来自 2026-11-24 用户确认的修复要求。

## Global Constraints

- 保持定时扫描关闭，不实际点击加购按钮，不修改库存，不自动修改历史结果。
- 复用现有扫描状态、证据路径、告警与配送设置；无需数据库迁移。
- 只判断 Live 商品页的加购健康。仅截图输入缺少 DOM 证据，记录 OCR 结果，不判为健康；保留原有仅截图的明确不可购买规则。
- 不伪造邮编生效结果，不将空白、页面未就绪或证据冲突当作库存异常。
- 代码修改完成后同步 `CHANGELOG.md`；未获授权不暂存、提交或推送。

## 验收规则

| 场景 | 结果 |
|---|---|
| 可用 DOM 加购按钮，且当次非空白 ROI 正常识别加购文案 | `healthy` |
| 按钮可用，但 OCR 为空、未匹配或识别失败 | `technical_failure`，保留 OCR 和截图诊断 |
| 有效商品页确认无可用按钮，且截图与 ROI 可用 | 保留现有无按钮库存风险规则 |
| 商品页未就绪、按钮状态无法确认、截图或 ROI 补拍后仍为空 | `technical_failure`，不触发库存告警 |
| 邮编输入值正确，但页面配送区未读到目标邮编 | 记录 `DELIVERY_REGION_UNVERIFIED`；不把此次邮编测试算作通过 |

售卖状态的既有配送降级策略保持不变，只有页面和图像证据都充分时才继续判断。

## Review Focus

- 配送提交触发重新渲染，即使之前已有标题，拍摄前也要重新等待。任务 1。
- 整页可能只有页头，单靠分辨率或非白像素数量无法证明商品主体已呈现。任务 1、2。
- 白色背景上的正常按钮文字应通过检查，整页有内容但 ROI 全白应补拍。任务 2。
- DOM 可用、OCR 为空或报错时，扫描与告警复查都应使用技术故障结果。任务 3。
- 邮编 `00174` 前导零、英国邮编空格及用户显式覆盖值在仓储和浏览器中保持。任务 4。

### 任务 1 / 配送后重新确认商品页

**文件**：`app/monitoring/adapters/playwright_scanner.py`、`tests/test_playwright_scanner.py`。

- [ ] 编写回归测试，复现标题先出现、配送后消失、随后可见的时序。验证截图只在配送后的检查通过时发生。
- [ ] 提取并复用就绪检查，配送提交和弹窗处理后再次确认目标商品页及可见的非空标题。等待使用有上限的预算；超时走技术故障并保留诊断截图。
- [ ] 测试配送设置失败但页面有效，以及配送后始终无标题两种情形。后者不进入 OCR。

### 任务 2 / 识别空白证据并补拍

**文件**：`app/monitoring/adapters/playwright_scanner.py`、`app/monitoring/adapters/roi.py`、`tests/test_playwright_scanner.py`、`tests/test_roi.py`。

- [ ] 用真实 PNG 构造白色整页、仅页头有画面、白色 ROI 和有文字的浅底 ROI，验证空白检测不误拦正常白底页面。
- [ ] 用 Pillow 校验可解码性、尺寸和近乎纯色的图像；整页同时检查标题所在商品区域，避免页头通过检测。按钮存在时核对用于取图的候选与用来判断的候选一致。
- [ ] 首次发现空白时重新等待页面稳定，并补拍一组整页和 ROI。补拍仍为空返回明确的 `SCREENSHOT_BLANK` 或 `ROI_BLANK`，保留诊断证据。只把最终有效的一组图交给 OCR，避免混用不同渲染时刻的证据。

### 任务 3 / Live 健康双证据判定

**文件**：`app/monitoring/application/real_observation.py`、`tests/test_real_observation_cross_validation.py`、相关只用截图的判定测试。

- [ ] 改写并补充断言。可用按钮加 OCR 命中为健康；可用按钮加空 OCR、未命中、识别失败均为技术故障；纯 OCR 命中只能保存文字证据；有效页面的明确无按钮样例保留库存风险逻辑。
- [ ] 实现判定并用现有多语言词库匹配，记录不一致原因。禁止技术故障触发库存告警或作为告警恢复证据。

### 任务 4 / 用户邮编与真实验收

**文件**：`tests/test_product_entry.py`、`tests/test_playwright_scanner.py`、`CHANGELOG.md`。

- [ ] 用录入接口和仓储验证站点邮编原样读回，再用受控 Chromium 页面验证填入对应配送控件、提交、页面更新和采集阶段顺序。
- [ ] 使用包含本次改动的新版本服务，对用户录入的意大利样例 `TEST-DE-B0CQMFJ777` 核对数据库中的自定义邮编 `10015`、实际提交值和页面重新渲染后配送区显示的值。只有读回一致才算邮编生效。若该商品不适合作为健康样例，另选已有健康样例。
- [ ] 依项目规则跑预期健康及明确无按钮的异常 Amazon 样例各一次，核对真实截图、ROI、OCR、扫描记录和告警。遇到网络限制或页面不可用，报告实际结果。
- [ ] 执行 `python -m unittest discover -s tests` 和 `git diff --check`，在 `CHANGELOG.md` 记录一条变更及验证结果。
