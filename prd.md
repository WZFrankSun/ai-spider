# 商品加购入口库存风险监控 Agent PRD

## 1. 文档信息

- 文档状态：第一版需求定义
- 目标市场：德国、意大利
- 第一版监控规模：两国合计 20 个商品，建议每国约 10 个
- 扫描频率：每小时一次
- 通知渠道：第一版只记录告警事件，飞书 Webhook 作为后续扩展
- 主要用户：跨境电商运营人员、库存管理人员、技术维护人员

## 2. 背景与问题

商品库存不足或平台库存数据异常时，商品详情页可能不显示“加入购物车”入口。该状态会直接影响用户下单和销售业绩，但运营人员通常只能通过人工访问商品页面发现。

现有项目已经具备 Playwright 浏览器自动化、平台配置、页面截图、结构化提取和 AI 工具调用能力。本产品在此基础上增加定时扫描、局部 OCR、异常事件记录和修复验证能力，用于提前发现商品无法加购的风险。

第一版的业务判断规则是：页面已经正常加载并成功截图时，如果加入购物车区域没有识别到配置词库中的目标词汇，则创建库存风险告警。

## 3. 产品目标

### 3.1 目标

1. 每小时检查德国和意大利市场的 20 个重点商品。
2. 通过截图和 ROI OCR 判断加入购物车入口是否出现。
3. 在一次有效扫描未识别到加入购物车词汇时立即记录库存风险。
4. 运营修复库存后，通过自动复查确认页面恢复。
5. 减少健康截图的存储量，并保留异常处理所需的证据。

### 3.2 非目标

- 不自动修改 Amazon、Shopify 或其他平台的库存。
- 第一版不通过点击购物车验证完整下单链路。
- 不通过 IP 地理位置判断国家。
- 不自动发现全站商品。
- 不使用云端 OCR 服务上传商品截图。
- 第一版不覆盖移动端响应式布局。
- 第一版不接入飞书 Webhook。
- 不把页面打不开、截图失败或 OCR 引擎失败直接判定为库存不足。

## 4. 用户与使用场景

### 4.1 主要用户

- 运营人员查看异常商品，调整平台库存数据并确认修复结果。
- 库存管理人员处理商品库存和销售状态。
- 技术人员维护扫描任务、平台配置、ROI 区域和 OCR 词库。

### 4.2 典型场景

1. 系统按小时打开德国 Amazon 商品页面。
2. 页面加载完成后截取商品详情页。
3. 系统只裁剪加入购物车区域并进行本地 OCR。
4. 如果没有识别到目标词汇，创建 `PRODUCT_ADD_TO_CART_MISSING` 事件。
5. 运营检查商品库存并修改平台库存数据。
6. 运营将事件标记为待验证，系统重新截图和 OCR。
7. 如果识别到加入购物车词汇，事件标记为已恢复。

## 5. 第一版范围

### 5.1 市场

| 国家 | 国家代码 | 语言环境 | 货币 | 第一版数量建议 |
|---|---|---|---|---:|
| 德国 | `DE` | `de-DE` | EUR | 约 10 个 |
| 意大利 | `IT` | `it-IT` | EUR | 约 10 个 |

国家归属由扫描任务显式配置。Cookie、页面语言、币种和配送信息只作为辅助证据保存，不作为主要国家判断依据。

### 5.2 商品清单

第一版使用版本化 JSON 或 CSV 静态清单。每条商品记录代表一个国家市场中的一个商品，即使两个国家暂时使用相同 URL，也需要建立两条独立记录。

建议 JSON 结构：

```json
{
  "country": "DE",
  "platform": "amazon",
  "sku": "SKU-001",
  "url": "https://example.com/product-001",
  "page_type": "product_detail",
  "roi_profile": "amazon_product_detail_de",
  "enabled": true
}
```

字段要求：

- `country`：`DE` 或 `IT`
- `platform`：平台名称
- `sku`：内部商品标识
- `url`：该国家实际扫描 URL
- `page_type`：页面类型，第一版主要为 `product_detail`
- `roi_profile`：ROI 配置名称
- `enabled`：是否参与扫描

## 6. 功能需求

### 6.1 定时扫描

- 默认每小时执行一次。
- 每个扫描周期读取最新商品清单。
- 只扫描 `enabled=true` 的记录。
- 第一版支持 20 条商品记录。
- 使用有限并发执行，建议同时运行不超过 3 个浏览器任务。
- 当前周期必须在下一周期开始前完成，无法完成时创建技术故障事件。
- 调度时间使用统一时区配置，展示时间包含时区信息。

### 6.2 浏览器环境

每个平台配置固定浏览器环境：

- 固定视口宽高。
- 固定语言环境。
- 固定页面等待条件。
- 固定 Cookie 弹窗处理逻辑。
- 商品区域和必要选择器加载完成后再截图。

第一版不模拟德国或意大利本地 IP。国家市场通过商品任务中的 `country` 字段确定。

### 6.3 截图

每次扫描流程：

1. 打开商品 URL。
2. 等待 DOM 加载和商品区域出现。
3. 处理已配置的 Cookie 或继续访问弹窗。
4. 等待平台配置的必要选择器出现。
5. 保存用于本次检测的页面截图。
6. 根据 ROI 配置裁剪加入购物车区域。

异常扫描必须保存：

- 完整页面截图
- ROI 裁剪截图
- 截图时间
- 商品和国家标识
- 页面 URL
- 页面标题

### 6.4 ROI 配置（**中译：感兴趣区域**）

ROI:基本定义是：**在整张图像中，指定给 OCR 引擎去识别的那一块子区域**，而不是让引擎对整幅图做全量识别。

深入解读：一张图里可能包含**大量与目标文字无关**的内容，比如背景、logo、表格线、其他栏目的文字。ROI 就是先用**坐标**（通常是矩形框，如 `x, y, width, height`）圈出你真正关心的部分，OCR 只在这个范围内做检测和识别。这样做的好处是减少计算量、降低误识别、提高关键字段的准确率。从流程上看，ROI 通常出现在 OCR 的**预处理或检测阶段之前**：先定位 ROI，再对 ROI 内部做二值化、倾斜校正、字符分割或直接送入识别模型。

ROI 按“平台 + 页面类型”配置，必要时支持国家维度覆盖。优先使用相对比例坐标，避免固定像素受视口变化影响。

建议结构：

```json
{
  "id": "amazon_product_detail_de",
  "platform": "amazon",
  "page_type": "product_detail",
  "viewport": {
    "width": 1440,
    "height": 900
  },
  "region": {
    "left": 0.65,
    "top": 0.55,
    "right": 0.98,
    "bottom": 0.90
  },
  "selector": null,
  "enabled": true
}
```

如果平台页面可以稳定定位购买区域，可以使用 CSS 选择器截取元素区域。选择器不可用时使用相对比例坐标。

### 6.5 本地 OCR

- OCR 必须在本地执行。
- 第一版覆盖英文、德文和意大利文。
- OCR 只处理 ROI 区域，不扫描整张图片作为主要判断依据。
- OCR 前允许进行放大、灰度化、对比度增强和去噪。
- 保存 OCR 原文、归一化文本、置信度和识别框信息。
- OCR 失败属于技术故障。

### 6.6 加购词库

词库按“国家 + 平台 + 页面类型”配置，支持多个同义表达。第一版至少包含：

| 语言 | 示例词汇 |
|---|---|
| 英文 | `Add to cart`、`Add to basket` |
| 德文 | `In den Warenkorb`、`In den Einkaufswagen`、`Zum Warenkorb` |
| 意大利文 | `Aggiungi al carrello`、`Aggiungi al cestino` |

匹配前对 OCR 文本进行以下归一化：

- 转换大小写。
- 合并连续空格。
- 统一标点和连字符。
- 保留并兼容德文、意大利文重音字符。
- 支持配置同义词和可接受的 OCR 变体。

词库示例：

```json
{
  "country": "IT",
  "platform": "amazon",
  "page_type": "product_detail",
  "phrases": [
    "Aggiungi al carrello",
    "Aggiungi al cestino",
    "Add to cart",
    "Add to basket"
  ]
}
```

### 6.7 异常判定

#### 库存风险

满足以下条件时创建 `PRODUCT_ADD_TO_CART_MISSING`：

- 页面成功打开。
- 商品区域按要求加载。
- 完整截图和 ROI 截图成功生成。
- OCR 成功执行。
- 归一化 OCR 结果中没有匹配词库中的任何目标词汇。

单次有效扫描即触发异常，不等待连续失败。

#### 技术故障

以下情况创建或更新 `MONITORING_TECHNICAL_FAILURE`：

- 页面打不开。
- 页面加载超时。
- 必要商品选择器未出现。
- 截图失败。
- ROI 裁剪失败。
- OCR 引擎异常。

技术失败在当前扫描周期内自动重试 2 次，每次使用退避等待。三次都失败后记录技术故障事件。

## 7. 告警与事件状态

第一版不发送飞书消息。系统必须保存结构化告警事件，后续可由飞书 Webhook 或其他通知渠道消费。

### 7.1 事件类型

- `PRODUCT_ADD_TO_CART_MISSING`：有效截图中缺少加入购物车文字。
- `MONITORING_TECHNICAL_FAILURE`：页面、截图或 OCR 技术失败。

### 7.2 事件状态

- `OPEN`：首次发现异常。
- `ACKNOWLEDGED`：运营已查看。
- `PENDING_VERIFICATION`：运营已处理库存，等待系统复查。
- `RESOLVED`：复查识别到加入购物车文字。
- `REOPENED`：复查仍未识别到加入购物车文字。
- `EXPIRED`：超过保留期限且未继续处理。

### 7.3 去重规则

- 同一个国家、平台、SKU 和异常类型只创建一个未关闭事件。
- 持续异常时更新失败次数、最近失败时间和最近证据路径。
- 不为同一持续异常每小时重复创建新事件。
- 事件恢复后再次发生异常时创建新的事件，保留历史关联。

## 8. 修复验证流程

1. 系统创建库存风险事件。
2. 运营查看商品、国家、OCR 结果和异常截图。
3. 运营调整平台库存数据。
4. 运营将事件状态改为 `PENDING_VERIFICATION`。
5. 系统下一次扫描时强制截图和 OCR，不使用健康截图缓存。
6. 识别到目标词汇时改为 `RESOLVED`。
7. 未识别到目标词汇时改为 `REOPENED`，并更新异常证据。
8. 运营确认恢复后，人工删除异常图片。

## 9. 健康截图与异常图片保留

### 9.1 健康状态

- 健康扫描仍按小时执行。
- 当前健康截图只保留到下一次扫描完成。
- 下一次扫描完成后销毁上一张健康截图。
- 健康状态可以保留必要的 OCR 文本、匹配结果和扫描状态记录。

### 9.2 异常状态

- 异常时保存完整截图和 ROI 截图。
- 未处理异常图片最多保留 3 天。
- 处理并验证恢复后由人工删除异常图片。
- 图片删除不应删除告警事件的必要结构化记录，除非后续确认需要一起清理。

### 9.3 Cookie 数据

只保存以下 Cookie 摘要：

- Cookie 名称
- 域名
- 路径
- 过期时间
- 是否存在
- 脱敏摘要或哈希值

禁止将完整 Cookie 值写入截图元数据、告警记录、日志或通知内容。

## 10. 数据结构

### 10.1 扫描任务

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

### 10.2 扫描结果

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

### 10.3 告警事件

```json
{
  "event_id": "event-0001",
  "type": "PRODUCT_ADD_TO_CART_MISSING",
  "status": "OPEN",
  "country": "DE",
  "platform": "amazon",
  "sku": "SKU-001",
  "url": "https://example.com/product-001",
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

## 11. 现有项目复用

第一版应优先复用现有代码：

- [app/browser/browser_manager.py](D:/WZ_Project/ai-spider/app/browser/browser_manager.py)：浏览器和会话生命周期。
- [app/browser/browser_session.py](D:/WZ_Project/ai-spider/app/browser/browser_session.py)：页面、平台和运行变量。
- [app/platforms/registry.py](D:/WZ_Project/ai-spider/app/platforms/registry.py)：平台 YAML 加载。
- [app/tools/browser/screenshot.py](D:/WZ_Project/ai-spider/app/tools/browser/screenshot.py)：截图和页面就绪等待。
- [app/core/registry.py](D:/WZ_Project/ai-spider/app/core/registry.py)：工具注册。
- [app/core/executor.py](D:/WZ_Project/ai-spider/app/core/executor.py)：工具执行和错误封装。
- [app/workflows/crawl_list.py](D:/WZ_Project/ai-spider/app/workflows/crawl_list.py)：批量访问和结果导出模式。

新增能力建议以独立模块实现：

- 定时扫描调度器
- 商品清单加载器
- ROI 配置加载器
- 本地 OCR 适配器
- 加购词库匹配器
- 扫描结果存储
- 告警事件状态机
- 健康截图清理器
- 异常图片人工删除接口或命令

## 12. 运行流程

```text
读取商品清单
    ↓
按国家和平台加载扫描配置
    ↓
创建浏览器会话并打开商品 URL
    ↓
处理弹窗并等待商品区域
    ↓
截图并裁剪 ROI
    ↓
本地 OCR
    ↓
匹配国家和平台词库
    ├─ 匹配成功 → 健康结果，清理上一张健康截图
    ├─ 未匹配 → 创建库存风险事件，保存完整截图和 ROI 截图
    └─ 技术失败 → 重试 2 次，仍失败则创建技术故障事件
```

## 13. 验收标准

### 13.1 扫描

- 能读取包含德国和意大利商品的静态 JSON 或 CSV。
- 能按小时启动扫描任务。
- 能扫描启用的商品记录并记录国家、平台、SKU 和 URL。
- 能使用固定视口完成页面加载和截图。

### 13.2 OCR

- 能只对配置的 ROI 区域执行 OCR。
- 能识别英文、德文和意大利文词库。
- 能对大小写、空格、标点和重音字符进行归一化。
- 能保存 OCR 原文、匹配词汇和置信度。

### 13.3 异常

- 有效截图中没有目标词汇时立即创建库存风险事件。
- 页面或 OCR 技术失败时不创建库存风险事件。
- 技术失败在同一周期内最多重试 2 次。
- 持续异常不会每小时重复创建独立事件。

### 13.4 修复验证

- 运营可以把异常事件标记为待验证。
- 待验证商品下一次扫描必须重新截图和 OCR。
- 恢复识别到目标词汇时事件变为 `RESOLVED`。
- 仍未识别到目标词汇时事件变为 `REOPENED`。

### 13.5 存储

- 健康截图在下一次扫描完成后被清理。
- 未处理异常截图最多保留 3 天。
- 修复验证后支持人工删除异常图片。
- 完整 Cookie 值不出现在任何持久化记录中。

## 14. 后续扩展

以下内容不属于第一版：

- 飞书 Webhook 通知。
- 其他欧洲国家市场。
- 移动端视口扫描。
- 从 PIM、数据库或商品 API 自动同步商品清单。
- 多节点或分布式扫描。
- 通过 DOM 或真实点击动作验证加入购物车。
- 运营后台和图表化监控面板。
- 自动修改库存或自动执行补货操作。
