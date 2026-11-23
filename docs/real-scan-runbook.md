# 爬虫截图 OCR 验收手册

## 目标

第一阶段直接使用现有爬虫生成的截图和 JSON 清单，不重复访问商品页面。服务读取截图后只裁剪加购区域，交给本地 Tesseract OCR，再通过国家、平台和页面类型对应的词库判断状态。

## 截图清单格式

```json
{
  "screenshots": [
    {
      "product_id": "DE-amazon-SKU-001",
      "path": "output/screenshots/amazon/DE-amazon-SKU-001.png",
      "captured_at": "2026-11-20T00:00:00Z",
      "country": "DE",
      "platform": "amazon",
      "sku": "SKU-001"
    }
  ]
}
```

`path` 必须位于 `MONITORING_SCREENSHOT_ROOT` 下。截图清单中的 `product_id` 必须能在商品目录中找到；文件缺失、路径越界或重复映射都会产生 `technical_failure`。

## 本地配置

```text
MONITORING_MODE=real
MONITORING_INPUT_MODE=manifest
MONITORING_CATALOG_PATH=config/products.real.json
MONITORING_SCREENSHOT_MANIFEST_PATH=config/screenshots.manifest.json
MONITORING_SCREENSHOT_ROOT=.
MONITORING_ROI_PROFILES_PATH=config/roi_profiles.json
MONITORING_PHRASE_SETS_PATH=config/phrase_sets.json
MONITORING_ARTIFACT_ROOT=output/artifacts
MONITORING_DATABASE_URL=mysql+aiomysql://<user>:<password>@127.0.0.1:3306/cart_monitor
TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
TESSERACT_LANGUAGES=eng+deu+ita
MONITORING_SCHEDULER_ENABLED=false
```

先使用 `MONITORING_SCHEDULER_ENABLED=false` 手动调用单个商品扫描，确认 ROI、OCR 和词库后再开启每小时调度。

## 状态规则

- OCR 匹配 `Add to cart`、`Add to basket`、德语或意大利语加购词：`healthy`。
- OCR 成功但未匹配加购词：`inventory_risk`，并创建或更新库存风险告警。
- 截图缺失、ROI 失败、Tesseract 缺失或 OCR 超时：`technical_failure`，不自动关闭库存风险告警。

## 验收顺序

1. 每个国家和平台先接入一个授权商品截图。
2. 用一张包含加购文字的截图验证 `healthy`。
3. 用一张移除加购文字的截图验证 `inventory_risk` 和告警。
4. 删除或损坏截图，验证 `technical_failure`。
5. 检查 API 中只出现 Cookie 摘要，不出现 Cookie 原文。
6. 单商品观察窗口通过后，再扩展到 DE/IT 共 20 个商品和每小时调度。

当前 Tesseract 系统二进制尚未安装时，Real 模式会在启动前明确失败，Demo 模式仍可启动。
