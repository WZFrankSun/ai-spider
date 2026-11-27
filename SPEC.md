# 商品加购入口库存风险监控 Agent Specification

## 1. 文档目的

本文档是可执行的技术规格，把 PRD 的业务目标落实为实现约束。文档内容按**当前代码实际状态**反写：已实现部分给出确切的行为与取值，规划部分明确标注「规划中」。

业务背景、范围与验收标准见 [prd.md](prd.md)。本文档不重复业务叙述。

三层关系：

- `prd.md`——业务视角：目标、范围、业务规则、验收。
- `SPEC.md`（本文）——实现视角：模块、接口、数据结构、判定逻辑、错误码、配置项。
- `docs/ARCHITECTURE.md`——技术选型与数据设计依据。

## 2. 系统概览

模块化单体，一个 Python 进程提供 HTTP 接口。核心链路：

```text
HTTP / 调度入口
  → ScanProduct（应用层）
    → Scanner 端口（适配器）
      ├─ PlaywrightScanner   实时抓取
      └─ CrawlerScreenshotScanner  离线截图清单（manifest 模式）
    → RealObservationFactory  DOM + OCR 双证据判定
  → 仓储端口（内存 / MySQL）
  → ArtifactStore（本地证据目录）
```

分层约束（不可违反）：

| 层 | 目录 | 禁止依赖 |
|---|---|---|
| 领域层 | `app/monitoring/domain/` | FastAPI、Playwright、SQLAlchemy、Tesseract |
| 应用层 | `app/monitoring/application/` | 具体浏览器、OCR、数据库类型 |
| 适配器层 | `app/monitoring/adapters/`、`app/browser/`、`app/platforms/` | — |

应用层只接收 `ScanObservation` 和 `OcrResult`，不感知具体实现。

## 3. 运行时模式与配置

### 3.1 两种运行模式

| 模式 | `MONITORING_MODE` | 说明 |
|---|---|---|
| demo | `demo` | 内存商品 + `DemoScanner`，确定性结果，不依赖外网 |
| real | `real` | Playwright 实时抓取 + MySQL + Tesseract |

real 模式启动前执行 preflight 校验（`validate_real_prerequisites`），任一项不满足直接拒绝启动，不静默降级。

### 3.2 两种输入模式

| 模式 | `MONITORING_INPUT_MODE` | 扫描器 |
|---|---|---|
| manifest | `manifest` | `CrawlerScreenshotScanner`，读取 `config/screenshots.manifest.json` 中的离线截图 |
| live | `live` | `PlaywrightScanner`，实时打开商品页 |

生产走 `live`。

### 3.3 配置项

全部通过 `.env` 或环境变量读取（`load_monitoring_config`，支持 `.env` 文件与系统环境变量，环境变量优先）。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MONITORING_MODE` | `demo` | `demo` / `real` |
| `MONITORING_INPUT_MODE` | `manifest` | `manifest` / `live` |
| `MONITORING_CATALOG_PATH` | `config/products.real.json` | 商品清单 |
| `MONITORING_SCREENSHOT_MANIFEST_PATH` | `config/screenshots.manifest.json` | 离线截图清单 |
| `MONITORING_SCREENSHOT_ROOT` | `.` | 截图根目录 |
| `MONITORING_ROI_PROFILES_PATH` | `config/roi_profiles.json` | ROI 配置 |
| `MONITORING_PHRASE_SETS_PATH` | `config/phrase_sets.json` | 词库 |
| `MONITORING_ARTIFACT_ROOT` | `output/artifacts` | 证据存储根目录 |
| `MONITORING_DATABASE_URL` | 空 | real 模式必填 |
| `MONITORING_SCHEDULER_ENABLED` | `false` | 进程内调度器开关 |
| `MONITORING_SCAN_INTERVAL_SECONDS` | `3600` | 调度间隔，**业务调整后应改为 `86400`** |
| `MONITORING_MAX_CONCURRENCY` | `3` | 并发上限 |
| `MONITORING_SCAN_TIMEOUT_SECONDS` | `120` | 单商品超时 |
| `TESSERACT_CMD` | 空 | 空则从 PATH 查找 `tesseract` |
| `TESSERACT_LANGUAGES` | `eng+deu+ita` | OCR 语言包 |
| `OCR_SCALE` | `3` | OCR 前放大倍数 |

数值型配置读取时校验必须为正数，非法值直接抛 `ValueError`，不做静默兜底。

### 3.4 调度职责

**workbuddy skill 是主调度方**，服务内置调度器（`MONITORING_SCHEDULER_ENABLED`）定位为手动/兜底排查工具，默认关闭。

两者**不可同时开启**，否则同一批商品会被重复扫描。生产配置应保持 `MONITORING_SCHEDULER_ENABLED=false`。

## 4. 站点与邮编

### 4.1 站点表

`app/monitoring/config/markets.py`：

```python
DEFAULT_POSTAL_CODES = {
    "DE": "10115", "IT": "00174", "FR": "75001", "ES": "28001",
    "GB": "SW1A 1AA", "NL": "1012", "SE": "111 22", "BE": "1049", "PL": "00-001",
}
AMAZON_DOMAINS = {
    "DE": "amazon.de", "IT": "amazon.it", "FR": "amazon.fr", "ES": "amazon.es",
    "GB": "amazon.co.uk", "SE": "amazon.se", "BE": "amazon.com.be",
    "PL": "amazon.pl", "NL": "amazon.nl",
}
AMAZON_LOCALES = {
    "DE": "de-DE", "IT": "it-IT", "FR": "fr-FR", "ES": "es-ES",
    "GB": "en-GB", "SE": "sv-SE", "BE": "fr-BE", "PL": "pl-PL", "NL": "nl-NL",
}
```

`ENTRY_COUNTRIES` 为全部 9 站，`LIVE_AMAZON_COUNTRIES` 与之相同。

### 4.2 邮编规则

**一个站点一个邮编，不做多邮编监测。** 邮编只从站点表取，不存商品上（003 迁移已删除 `product.postal_code` 字段）。

- 缺站点配置 → `POSTAL_CODE_REQUIRED`，直接终止扫描。
- 不允许跳过配送设置继续扫描。

### 4.3 邮编规范化与匹配

`app/monitoring/config/postal_codes.py`：

```python
_POSTAL_FORMATTING = str.maketrans("", "", "-\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad")
```

即剥离：连字符 `-`、零宽空格/非连接符/连接符、左右方向标记、BOM、软连字符。

- `normalize_postal()`：去空白、去连字符、去零宽字符与软连字符、转大写。
- `postal_values_equal()`：归一化后全等比较。
- `postal_matches(readback, target)`：**正则匹配**，不是简单相等。

`postal_matches` 的判定逻辑：

```
text = readback.translate(_POSTAL_FORMATTING).upper()
candidate = r"\s*".join(re.escape(character) for character in expected)
return re.search(r"(?<![^\W_])" + candidate + r"(?![^\W_])", text) is not None
```

要点：

- 候选内部允许排版空白（`SW1A 1AA` ↔ `SW1A1AA`），两端必须完整。
- 前后用 `(?<![^\W_])` / `(?![^\W_])` 保留页头空白的词边界作用，否则邮编会与城市名粘连。
- **要求完整值匹配**——`101150` 不会被认成 `10115`。
- 读回为空或目标为空一律返回 `False`。

## 5. 商品配置

### 5.1 清单文件

`config/products.real.json`，结构 `{ "products": [...] }`。

`CatalogProductRecord`（`app/monitoring/config/catalog_schema.py`）使用 Pydantic，`extra="forbid"`：

| 字段 | 约束 |
|---|---|
| `id` | 非空 |
| `country` | 自动 `strip().upper()` |
| `platform` | 非空 |
| `sku` | 非空 |
| `url` | 非空 |
| `page_type` | 默认 `product_detail` |
| `roi_profile` | 非空 |
| `name` | 默认空串 |
| `enabled` | `StrictBool`，默认 `true` |

### 5.2 录入校验

`ProductEntryRequest`（`app/monitoring/api/schemas.py`）：

- `platform`：`amazon` / `tiktok` / `temu` / `ebay` / `shein`
- `store_code`：`H1-A1` / `H2-A1` / `H4-A1`
- `added_by`：`Frank` / `Lvy` / `Nova` / `Drake`
- `country`：必须非空且属于 `ENTRY_COUNTRIES`
- 链接必须 HTTPS、无用户名端口、域名与平台/站点一致、路径非根
- Amazon 必须有合法 ASIN，且与填写的 `asin` 一致（不区分大小写）

录入时 `roi_profile_id` 自动按 `amazon_product_detail_{country小写}_buy_box` 生成（仅 Amazon）。

### 5.3 去重

同一 `(country, platform, store_code, sku.casefold())` 视为同一商品，重复录入返回 `409` 并附带已有 `product_id`。

删除记录写入 `deleted_product_ids` 表（004 迁移），避免重启补录时重新灌入已删商品。

## 6. 平台配置

`app/platforms/ecommerce/amazon.yaml`。关键项：

```yaml
browser:
  viewport: {width: 1440, height: 900}

cookies:
  reject: '#sp-cc-rejectall-link, button:text-is("Ablehnen"), button:text-is("Reject"), button:text-is("Refuser"), button:text-is("Rifiuta")'

location:
  trigger: "#nav-global-location-popover-link"
  postal_input: "#GLUXZipUpdateInput"
  submit: "#GLUXZipUpdate .a-button-input"
  confirm: "button:has-text('Fertig')"
  result: "#glow-ingress-block"
  continue_selectors: [...]   # 9 站全部文案
```

### 6.1 Cookie 拒绝选择器

**首选内部 id**（`#sp-cc-rejectall-link`，跨语言不变），后接各站语言文字兜底。站点没配对应语言时靠内部 id 兜住。

### 6.2 配送弹窗（两段式）

```text
trigger      点页头「Lieferung nach ...」打开弹窗
postal_input 填邮编
submit       填完点提交
confirm      再点「Fertig」，配送地才真正生效
result       页头配送栏，用于回读验证
```

`trigger` / `postal_input` / `submit` / `result` 都是亚马逊内部 id，跨站点一致；`confirm` 只有德语文案，其余语言走代码兜底查找（`_find_delivery_confirm`）。

### 6.3 继续购物选择器

`location.continue_selectors` 是一个列表，按顺序逐个尝试。**新增站点必须补上该站语言的文案，漏配会停在中间页并报 `READY_SELECTOR_MISSING`。**

西班牙站必须用 `text-is` 而非 `has-text`：该页提示语里也含 "seguir comprando"，`has-text` 会命中提示文本所在的容器而不是按钮。

当前已配语言：英语、法语、德语、意大利语、西班牙语、荷兰语、瑞典语、波兰语。

### 6.4 就绪选择器

`extraction.page_types.product_detail.ready_selectors`：`#productTitle`
可选：`#landingImage`

## 7. 扫描流程

`app/monitoring/adapters/playwright_scanner.py`。

### 7.1 超时预算

| 参数 | 默认 | 作用域 |
|---|---|---|
| `timeout_ms` | 30 秒 | 单个通用操作（导航、点击、等选择器） |
| `delivery_timeout_ms` | 20 秒 | 整个配送设置流程总闸 |
| 就绪选择器等待 | `min(timeout_ms, 10s)` | 每个 ready selector |
| Cookie 拒绝按钮等待 | `min(timeout_ms, 6s)` | 可见即点 |
| 配送邮编框等待 | `min(timeout_ms, 8s)` | 按可见状态 |
| 按钮截图 | `min(timeout_ms, 3s)` | ROI 裁剪 |
| 继续购物点击 | `min(timeout_ms, 5s)` | — |

### 7.2 流程

```text
1. requires_delivery = (platform == "amazon")
   → 取站点邮编；amazon 且取不到 → POSTAL_CODE_REQUIRED 终止
2. 加载平台配置；找不到 → PLATFORM_NOT_FOUND
3. browser_manager.start() 失败 → BROWSER_START_FAILED
4. create_session(viewport, locale) 失败 → SESSION_CREATE_FAILED
   locale：amazon 用 AMAZON_LOCALES[country]，否则 profile.browser.locale，默认 en-US
5. page 为空 → PAGE_NOT_AVAILABLE
6. page.goto(url, wait_until="domcontentloaded")
   超时 → NAVIGATION_TIMEOUT；其他异常 → NAVIGATION_FAILED
7. 点「继续购物」→ 重开原商品链接 → 拒绝 Cookie
   异常 → READY_SELECTOR_FAILED（保留诊断截图）
8. 逐个 wait_for_selector(selector, state="attached", timeout=min(timeout_ms,10s))
   超时 → READY_SELECTOR_MISSING（保留诊断截图）
9. 商品页就绪后再次尝试拒绝 Cookie
   异常 → READY_SELECTOR_FAILED
10. 配送设置（仅 amazon），总闸 delivery_timeout_ms
    失败 → 终止扫描，保存 delivery_failed.png 诊断图
11. 截图 → 裁 ROI → OCR
12. RealObservationFactory 判定
```

### 7.3 重开商品链接

「继续购物」的落点可能是首页或中间页，因此统一重开原商品链接再处理商品页弹窗。导航中断（`net::ERR_ABORTED`）时允许单次恢复：仅在确认落到同站首页后重开原商品。

### 7.4 配送设置细节

```text
打开弹窗 → 等邮编框可见（≤8s）→ 兜底查找邮编框 → 读当前值
  → 值与目标一致：直接进入提交
  → 值不一致：清空并 type(postal_code, delay=60, timeout=8000) → 再读值校验
  → 不一致 → 报错（报告期望值与实际值）
→ 点 submit → 等确认按钮 → 点 confirm
→ 关闭弹窗 → 读页头 result 区域
  → postal_matches(读回, 目标) 为 False → DELIVERY_REGION_UNVERIFIED
```

邮编框兜底查找按属性关键字匹配（`postal` / `postcode` / `postleitzahl` / `plz` / `zip` / `postnummer` / `codice postale` / `kod pocztowy`），并排除隐藏控件与页头搜索框。

**配送设置失败必须终止扫描，不能降级继续**——配送地直接决定加购按钮的判定基准。

### 7.5 错误码

`ScanErrorCode`：

| 错误码 | 含义 |
|---|---|
| `PLATFORM_NOT_FOUND` | 平台配置不存在 |
| `BROWSER_START_FAILED` | 浏览器启动失败 |
| `SESSION_CREATE_FAILED` | 会话创建失败 |
| `PAGE_NOT_AVAILABLE` | 会话无 page |
| `NAVIGATION_TIMEOUT` | 导航超时 |
| `NAVIGATION_FAILED` | 导航异常 |
| `READY_SELECTOR_MISSING` | 必要选择器未出现（**不重试**） |
| `READY_SELECTOR_FAILED` | 选择器等待/弹窗处理异常 |
| `SCREENSHOT_FAILED` | 截图失败 |
| `SCREENSHOT_BLANK` | 截图空白 |
| `ROI_BLANK` | ROI 裁剪结果空白 |
| `ARTIFACT_SAVE_FAILED` | 证据保存失败 |
| `ROI_FAILED` | ROI 裁剪失败 |
| `OCR_NOT_CONFIGURED` | OCR 未接入 |
| `POSTAL_CODE_REQUIRED` | 缺少站点邮编 |
| `DELIVERY_REGION_UNVERIFIED` | 配送地回读校验失败 |
| `OBSERVATION_BUILD_FAILED` | 观测构造失败 |
| `UNEXPECTED_SCAN_ERROR` | 未预期异常 |

## 8. DOM + OCR 双证据判定

`app/monitoring/application/real_observation.py`。这是本系统最核心的逻辑，也是误报风险最高的地方。

### 8.1 DOM 侧三态

```python
ADD_TO_CART_SELECTOR = (
    'button#add-to-cart-button, input#add-to-cart-button[type="submit"], '
    'input#add-to-cart-button[type="button"], #add-to-cart-button[role="button"]'
)
```

列出同一 id 的四种标签形态，因为不同站点的加购按钮有时是 `<button>`，有时是 `<input type="submit">`。

探测「可用」需同时满足三个条件：

1. `is_visible()`——有尺寸且没被遮挡。Cookie 或配送弹窗残留时按钮在 DOM 中但被遮住，会被判为不可见。
2. `is_enabled()`——没有 `disabled` 属性。
3. `click(trial=True, timeout=2000)`——Playwright 可操作性检查（能滚动到、能接收事件、不被别的元素挡住），**不发送真实点击**。

多报价商品会有多个同 id 按钮，逐个检查，遇到第一个可用的即返回。

返回 `(dom_state, element)`：

| dom_state | 条件 |
|---|---|
| `True` | 找到可用按钮 |
| `False` | 有候选但全部不可见/禁用 |
| `None` | 有候选可见但通不过可操作性检查，或探测本身异常 |

**`False` 与 `None` 的区分是判定安全性的关键：只有 `False` 才允许判库存风险。**

### 8.2 判定表

| DOM | OCR 加购词 | OCR 不可购词 | 状态 | error_code |
|---|---|---|---|---|
| `True` | 命中 | — | `healthy` | — |
| `True` | 未命中 | — | `technical_failure` | `DOM_OCR_MISMATCH` |
| `False` | 命中 | — | `technical_failure` | `DOM_OCR_MISMATCH` |
| `False` | 未命中 | — | `inventory_risk` | — |
| `None` | 命中 | — | `technical_failure` | `DOM_OCR_MISMATCH` |
| `None` | 未命中 | 命中 | `inventory_risk` | — |
| `None` | 未命中 | 未命中 | `technical_failure` | `OCR_AVAILABILITY_UNVERIFIED` / `OCR_AVAILABILITY_CONFLICT` |

判定原则：**两者一致才下结论，矛盾时宁可报技术故障也不猜。**

特殊情况说明：

- `dom_state=False` 时不强制要求不可购文案佐证——西班牙站无货时只显示愿望单按钮，不写任何不可购买文案。
- `dom_state=None` 且 OCR 明确读到不可购文案时也判库存风险。
- OCR 引擎抛异常 → 技术故障，错误码取异常的 `code` 或 `OCR_FAILED`。
- 词库加载失败 → 技术故障，`PHRASE_SET_LOAD_FAILED`。

## 9. OCR 与词库

### 9.1 OCR 适配器

`app/monitoring/adapters/ocr_tesseract.py`，`TesseractOcrAdapter`。

- 使用 `image_to_data` 而非 `image_to_string`，为了同时拿到词块和置信度。
- `asyncio.to_thread` + `asyncio.wait_for` 实现异步封装，超时抛 `OcrError("OCR_TIMEOUT")`。
- 错误码：`INVALID_IMAGE`、`OCR_TIMEOUT`、`TESSERACT_NOT_FOUND`、`OCR_FAILED`。

### 9.2 放大

```python
DEFAULT_SCALE = 3
```

**按钮裁剪图通常只有 200×30 像素，Tesseract 在该尺寸下常把带附加符号的字母读错**，例如西班牙语 `Añadir` 被读成 `Afiadir`。放大后再识别可稳定还原字母本身，归一化阶段再剥离重音即可匹配词库。

放大只作用于送进 OCR 的副本，**存档证据仍为原始尺寸**；缩放失败退回原图。倍数由 `OCR_SCALE` 配置。

### 9.3 归一化

`app/monitoring/application/phrase_matching.py` 的 `normalize_ocr_text`：

1. NFKC 归一化——统一全角/半角、兼容字符。
2. 转小写。
3. NFKD 分解并去掉组合记号——剥离 `ñ`/`é`/`ü` 等附加符号。
4. 下划线换空格。
5. 非单词字符换空格。
6. 合并连续空白。

**剥离附加符号是刻意设计**：小语种文案普遍带重音或波浪号，OCR 未必能准确还原；两边都去符号后即可对齐。反之，若词库带符号而 OCR 读不出，会永远匹配不上。

### 9.4 匹配

`match_add_to_cart(text, phrases)` 尝试两种形态：

1. 归一化短语作为子串出现在归一化文本中。
2. 去掉所有空格后匹配——覆盖 OCR 把词内换行或多余空格打乱的情况。

返回首个命中的词库条目（`matched_phrase` 为词库原文，便于人工核对）。

### 9.5 词库文件

`config/phrase_sets.json`，结构 `{ "phrase_sets": [...] }`。每项：

```
{
  "country": "ES",
  "platform": "amazon",
  "page_type": "product_detail",
  "phrases": ["Anadir al carrito", ...],
  "unavailable_phrases": ["Anadir a la Lista de deseos", ...]
}
```

`JsonPhraseSetLoader.load(country, platform, page_type, unavailable=False)`：

- `unavailable=True` 取不可购词库，否则取加购词库。两套分开维护，用途不同。
- 站点维度是必要的——DOM 结构可以跨站通用（同样的 id），但显示文案必须按站点语言给。
- 词库不存在时抛 `PhraseSetError` 而非返回空列表——空词库会让所有商品都判不出结果，问题被推迟到判定阶段才暴露，排查成本更高。

当前 9 站词库数量：

| 站点 | `phrases` | `unavailable_phrases` |
|---|---:|---:|
| `DE` | 10 | 17 |
| `IT` | 7 | 18 |
| `FR` | 8 | 14 |
| `GB` | 4 | 5 |
| `ES` | 5 | 8 |
| `SE` | 5 | 5 |
| `BE` | 7 | 6 |
| `PL` | 4 | 7 |
| `NL` | 7 | 7 |

## 10. ROI 配置

`config/roi_profiles.json`，结构 `{ "profiles": [...] }`。`JsonRoiProfileLoader` 按 `id` 加载。

当前 10 条 profile，9 个站点各一条，`selector` 统一为 `#rightCol`，`region` 为 `null`：

```
amazon_product_detail_de_live        （DE，遗留 profile）
amazon_product_detail_de_buy_box
amazon_product_detail_it_buy_box
amazon_product_detail_fr_buy_box
amazon_product_detail_gb_buy_box
amazon_product_detail_es_buy_box
amazon_product_detail_se_buy_box
amazon_product_detail_be_buy_box
amazon_product_detail_pl_buy_box
amazon_product_detail_nl_buy_box
```

`RoiCropper` 优先用 CSS 选择器定位元素区域，不可用时回退到相对比例坐标（`region` 字段）。裁剪结果用 `has_image_content()` 校验，非空才送 OCR。

## 11. 状态模型与告警

### 11.1 商品扫描状态

| 状态 | 含义 |
|---|---|
| `not_scanned` | 尚未执行过扫描 |
| `scanning` | 当前正在执行扫描 |
| `healthy` | 有效巡检确认加购入口可用 |
| `inventory_risk` | 有效巡检确认无法加购 |
| `technical_failure` | 页面或识别环节失败，结果不可判定 |

```text
not_scanned → scanning → healthy
                       ├→ inventory_risk
                       └→ technical_failure
```

### 11.2 告警状态

```text
open → acknowledged → pending_verification → resolved
                                      └──────→ reopened
```

另有 `dismissed`。

`can_resolve_alert`（`app/monitoring/domain/policies.py`）要求四项同时成立：

```
(
    alert.type == AlertType.PRODUCT_ADD_TO_CART_MISSING
    and alert.status == AlertStatus.PENDING_VERIFICATION
    and observation.status == ProductScanStatus.HEALTHY
    and bool(observation.matched_phrase)
)
```

### 11.3 告警策略

`ScanProduct._apply_alert_policy`：

- 只有 `inventory_risk` 才触发告警逻辑，技术故障不创建也不关闭告警。
- 已有活动告警 → `failure_count += 1`；若原状态是 `pending_verification` 则转 `reopened`。
- 无活动告警 → 创建 `open` 告警，ID 为 `alert-{product_id}`（同一商品同时只有一个活动告警）。

`VerifyAlert.execute`：

- 复查前把告警置为 `pending_verification`。
- 复查后：`healthy` 且满足 `can_resolve_alert` → `resolved`；`inventory_risk` → `reopened` 且 `failure_count += 1`；其他 → 保持 `pending_verification`。
- 复查**不走重试包装**（`scan_with_retry`），直接调 `scanner.scan`。
- 复查异常时商品置 `technical_failure`，告警保持 `pending_verification`。

## 12. 重试策略

`app/monitoring/application/retry_policy.py` 的 `scan_with_retry`：

- `attempts` 默认 3（即最多重试 2 次）。
- 异常 → 退避后重试，最后一次抛出让应用层记录失败。
- 观测状态为 `technical_failure` → 退避后重试，**但 `READY_SELECTOR_MISSING` 直接返回不重试**（页面已就绪失败，重试同一页面无意义）。
- 状态非 `technical_failure`（即 `healthy` 或 `inventory_risk`）→ 立即返回。

## 13. 批量巡检

`app/monitoring/application/scheduled_scan.py` 的 `HourlyScanRunner`。

### 13.1 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `max_concurrency` | 3 | `asyncio.Semaphore` 控制并发 |
| `live_only` | `False` | real 模式下为 `True`，只扫 `supports_live_scan` 的商品 |
| `per_product_timeout_seconds` | 120 | 单商品超时 |

### 13.2 行为

```
enabled_products = await self.products.list_enabled()
if self.live_only:
    enabled_products = [p for p in enabled_products if supports_live_scan(p)]
```

每个商品包在 `asyncio.wait_for` 中：

- 超时 → `_mark_technical_failure`，错误 `SCAN_TIMEOUT`。
- 其他异常 → `_mark_technical_failure`，错误为异常字符串。

**单个商品失败不阻塞整轮。**

### 13.3 批次摘要

```
@dataclass
class ScanBatchSummary:
    started_at: datetime
    finished_at: datetime
    total: int
    healthy: int = 0
    inventory_risk: int = 0
    technical_failure: int = 0
    failed_product_ids: list[str] = field(default_factory=list)
```

`supports_live_scan`（`domain/policies.py`）：

```
product.platform == "amazon" and product.country in LIVE_AMAZON_COUNTRIES
```

### 13.4 循环调度

`app/monitoring/entrypoints/hourly_scan.py` 的 `run_forever(runner, interval_seconds=3600, stop_event)`：

- 先跑一轮，再 `wait_for(stop_event.wait(), timeout=interval_seconds)`。
- 收到停止信号立即退出，否则超时继续下一轮。

**业务调整为每天一次后，`MONITORING_SCAN_INTERVAL_SECONDS` 应设为 `86400`。** 但主调度由 workbuddy 承担，此内置循环仅作兜底。

## 14. 规划中：异步批量巡检接口

**当前状态：未实现。** 以下为按业务沟通确定的接口形态与约束。

### 14.1 接口

```
POST /api/scan-runs
  → 202 {"run_id": "<uuid>", "total": 40, "status": "running"}

GET /api/scan-runs/{run_id}
  → 200 {"run_id": "...", "status": "running|finished",
         "total": 40, "healthy": 0, "inventory_risk": 0,
         "technical_failure": 0, "failed_product_ids": [],
         "started_at": "...", "finished_at": null}
```

### 14.2 约束

- 复用 `HourlyScanRunner`，并发与超时沿用现有配置。
- 批次状态在内存中维护（运行期状态，不落库）。
- 同一时刻只允许一个批次运行；重复触发返回 `409`。
- 批次结果与商品状态、告警的写入与单商品扫描完全一致。

### 14.3 与 workbuddy skill 的职责边界

| 层 | 职责 |
|---|---|
| workbuddy skill | 定时触发、轮询进度、汇总人类可读报告、异常时通知 |
| 服务端 | 商品筛选、浏览器操作、配送设置、OCR、DOM+OCR 判定、告警去重、证据保存 |

**判定逻辑一律留在服务端。** skill 不自行判断商品状态，只消费服务端给出的 `status` 和摘要。

### 14.4 为什么不用同步长连接

40 商品、3 并发，单商品约 30–40 秒，一轮约 8–15 分钟。同步接口在此量级下会被客户端、代理或 uvicorn 前置超时打断，而扫描已跑了一半且无法续跑。

### 14.5 为什么不用 skill 循环调单商品接口

串行 40 个商品约 25 分钟；拿不到批次摘要；无并发控制（`BrowserManager` 为单例，并发调会争抢浏览器资源）；中断后无状态可恢复。

## 15. API 合同

### 15.1 通用

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 监控页面 |
| GET | `/api/health` | 服务状态与运行模式 |
| GET | `/api/monitoring/status` | 运行配置、调度状态、OCR 配置、preflight 结果 |
| GET | `/api/products` | 已启用商品与当前状态 |
| GET | `/api/products/manage` | 全部商品（仅 real 模式） |
| POST | `/api/products` | 录入商品（仅 real 模式），`201` |
| POST | `/api/products/batch-delete` | 批量删除（仅 real 模式） |
| GET | `/api/scans` | 巡检结果 |
| GET | `/api/scans/{scan_id}/screenshots/{kind}` | 截图（`kind` ∈ `full` / `roi`） |
| GET | `/api/alerts` | 告警列表 |
| POST | `/api/products/{product_id}/scan` | 执行一次扫描 |
| POST | `/api/alerts/{alert_id}/verify` | 标记处理并复查 |
| POST | `/api/alerts/{alert_id}/dismiss` | 关闭告警（误报） |
| POST | `/api/products/{product_id}/demo-result` | demo 模式设置下次结果（real 模式不暴露） |

规划中：`POST /api/scan-runs`、`GET /api/scan-runs/{run_id}`。

### 15.2 状态码约束

| 情形 | 状态码 |
|---|---|
| 未知商品或告警 | `404` |
| 同一商品已有扫描或复查 | `409` |
| 重复录入商品 | `409`（附带已有 `product_id`） |
| 平台或站点暂未支持扫描 | `409` |
| real 模式下调用商品管理接口 | `404` |
| 截图不存在或路径越界 | `404` |

### 15.3 截图访问安全

`GET /api/scans/{scan_id}/screenshots/{kind}` 做路径校验：

```
root = (Path.cwd() / "output" / "artifacts").resolve()
candidate = Path(raw_path).resolve()
candidate.relative_to(root)   # 越界则 404
```

只允许读取 `output/artifacts` 目录下的文件。

### 15.4 健康检查

`/api/health` 返回 `{"status": "ok", "mode": "demo"|"real"}`；real 模式额外返回 `scheduler_enabled` 与 `scheduler_running`。

## 16. 数据模型

### 16.1 MySQL 表

`app/monitoring/adapters/mysql/models.py`，Alembic 迁移 `001`–`004`：

| 表 | 说明 |
|---|---|
| `products` | 商品主表，含 `store_code`、`asin`、`added_by` |
| `deleted_product_ids` | 已删商品 ID 记录，防重启补录回灌 |
| `scan_runs` | 巡检结果，含 OCR 文本、错误码、截图路径、Cookie 摘要 |
| `alerts` | 告警，含 `failure_count`、`operator_note`、`metadata_json` |
| `alert_transitions` | 告警状态变更流水 |
| `artifacts` | 证据索引，含 `artifact_type`、`deleted_at` |
| `roi_profiles` | ROI 配置 |
| `phrase_sets` | 词库 |

关键列类型：`products.country` / `alerts` 等站点字段为 `String(2)`，`scan_runs.cookie_summary` 与 `metadata_json` 为 `JSON`。

### 16.2 领域模型

`app/monitoring/domain/models.py`：

- `Product`：`id`、`country`、`platform`、`sku`、`url`、`page_type`、`roi_profile_id`、`name`、`enabled`、`status`、`store_code`、`asin`、`added_by`。
- `ScanObservation`：`status`、`ocr_text`、`matched_phrase`、`confidence`、`error_code`、`error_message`、`started_at`、`finished_at`、`full_screenshot_path`、`roi_screenshot_path`、`cookie_summary`。
- `Scan`：`id`、`product_id`、`status`、`observation`、`started_at`、`finished_at`。
- `Alert`：`id`、`type`、`status`、`product_id`、`failure_count`、`operator_note`、`metadata`；`apply_observation()` 实现状态机。

**领域层不得导入** FastAPI、Playwright、SQLAlchemy、Tesseract、MySQL SDK。

## 17. 证据与 Cookie 生命周期

### 17.1 图片保留

`app/monitoring/application/artifact_retention.py` 的 `ArtifactRetentionService`（`unprocessed_days=3`）：

| 记录类型 | 删除条件 |
|---|---|
| `healthy` | 属于「本轮已完成巡检」的健康证据集合 |
| 已处理 | `resolved` 且在人工删除名单中 |
| 未处理异常 | 创建时间距今 ≥ 3 天 |

删除图片**不删除**告警与巡检的结构化记录。

### 17.2 Cookie

`app/monitoring/application/cookie_summary.py` 的 `summarize_cookies` 只输出：名称、域名、路径、过期时间、是否存在、脱敏摘要或哈希值。

**完整 Cookie 值不得进入截图元数据、告警记录、日志或通知内容。**

## 18. 配置、运行与依赖

- Python 版本遵循 `pyproject.toml` 的 `requires-python`。
- 依赖用 `uv` 管理，锁文件 `uv.lock`。
- 全局 uv 缓存不可写时使用项目内缓存：`$env:UV_CACHE_DIR="$PWD\.uv-cache"`。
- 启动：`uv run python app.py`，监听 `127.0.0.1:8000`。
- demo 模式不依赖 Kafka、MySQL、OCR 模型或外部 API Key；real 模式新增依赖必须通过适配器和可选配置引入。

## 19. 测试与验收

### 19.1 测试布局

`tests/` 下 35 个测试文件（另有 `tests/integration/` 子目录），`unittest` 框架。当前 182 项测试。

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -t tests -p "test_*.py"
```

（`tests` 目录无 `__init__.py`，`-t` 必须指向 `tests` 本身，否则 `ImportError: Start directory is not importable`。）

### 19.2 关键测试点

| 测试文件 | 覆盖 |
|---|---|
| `test_real_observation.py` | DOM + OCR 判定各分支 |
| `test_real_observation_cross_validation.py` | 证据冲突与一致性 |
| `test_postal_codes.py` | 邮编规范化与完整值匹配 |
| `test_phrase_matching.py` | 归一化、去符号、两种匹配形态 |
| `test_playwright_scanner.py` | 弹窗流程、配送设置、超时 |
| `test_amazon_markets.py` | 站点文案与选择器配置 |
| `test_scan_retry.py` | 重试与 `READY_SELECTOR_MISSING` 不重试 |
| `test_scheduled_scan.py` | 批次摘要与并发 |
| `test_ocr_adapter.py` | 放大与错误码 |
| `test_artifact_retention.py` | 图片保留规则 |
| `test_runtime_config.py` | 配置校验 |
| `test_real_service_lifecycle.py` | 启动停止生命周期 |

### 19.3 Live 验收流程

每次代码修改后需执行 Live 验收（纯文档改动不适用）：

1. **先提醒用户在本机重启服务**，确认后核对服务进程启动时间晚于代码修改时间。
2. 选一个预期健康商品和一个预期无加购入口商品，各扫描一次。
3. 期望分别为 `healthy` 和 `inventory_risk`，并核对异常样例对应的库存告警。
4. **保持定时扫描关闭**，**不点击实际加购按钮**。
5. 商品状态变化、访问受限或扫描失败时，如实记录实际结果及未通过原因。

### 19.4 验收要点

- 9 站各自默认邮编正确写入并回读校验通过。
- `Añadir a la cesta` 与 `Anadir a la cesta` 匹配成功。
- `dom_state=None` 时不产生库存告警。
- 持续异常只累计 `failure_count`，不产生多条活动告警。
- 批次摘要的三个状态数量与实际巡检结果一致。

## 20. 与现有文档的关系

| 文档 | 作用 |
|---|---|
| `prd.md` | 业务目标、范围、业务规则与验收 |
| `SPEC.md`（本文） | 实现规格：模块、接口、数据结构、判定逻辑、配置 |
| `docs/ARCHITECTURE.md` | 技术选型、模块边界与数据设计依据 |
| `docs/real-scan-runbook.md` | 真实扫描操作手册 |
| `docs/production-readiness.md` | 生产就绪度检查项 |
| `docs/superpowers/plans/2026-11-26-scanner-interaction-and-postal-readback.md` | M1–M6 扫描器交互与邮编回读方案 |
| `AGENTS.md` | 项目操作规约与验收约定 |

`prd.md` 与本 SPEC 若有冲突，以本 SPEC 的实现描述为准，并回改 PRD。
