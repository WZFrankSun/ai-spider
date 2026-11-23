# Real 截图 OCR 配置

## 1. 安装 Tesseract

项目使用 `pytesseract` 调用本机 Tesseract 程序。Tesseract 上游文档说明，Windows 新版本通常使用 UB Mannheim 提供的安装包；安装后需要确认 `eng`、`deu`、`ita` 语言数据位于 `tessdata` 目录。

下载入口：

- [Tesseract Downloads](https://tesseract-ocr.github.io/tessdoc/Downloads)
- [UB Mannheim Windows installers](https://github.com/UB-Mannheim/tesseract/wiki)

安装后执行：

```powershell
tesseract --version
tesseract --list-langs
```

如果程序没有加入 PATH，在 `.env` 中指定：

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSERACT_LANGUAGES=eng+deu+ita
```

## 2. 准备真实配置

```powershell
Copy-Item config/products.real.example.json config/products.real.json
Copy-Item config/screenshots.manifest.example.json config/screenshots.manifest.json
Copy-Item config/roi_profiles.example.json config/roi_profiles.json
Copy-Item config/phrase_sets.example.json config/phrase_sets.json
```

把商品目录中的示例 URL、商品 ID 和 ROI 配置替换为明确授权的商品；把爬虫生成的截图放在 `MONITORING_SCREENSHOT_ROOT` 目录下，并在 manifest 中填写 `product_id`、`path` 或 `screenshot_path`、`captured_at`。

## 3. 验证 Real 前置条件

先在 `.env` 设置：

```env
MONITORING_MODE=real
MONITORING_INPUT_MODE=manifest
MONITORING_SCREENSHOT_ROOT=.
MONITORING_SCHEDULER_ENABLED=false
```

执行：

```powershell
uv run python -c "from app.monitoring.runtime_config import load_monitoring_config, validate_real_prerequisites; c=load_monitoring_config(); print(validate_real_prerequisites(c))"
```

输出空列表时，说明本地文件和 Tesseract 前置检查通过。第一次接入建议关闭调度，只扫描一个授权商品，确认截图、ROI 和词库后再打开每小时任务。
