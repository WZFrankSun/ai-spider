from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping


RuntimeMode = Literal["demo", "real"]
InputMode = Literal["manifest", "live"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class MonitoringRuntimeConfig:
    mode: RuntimeMode = "demo"
    input_mode: InputMode = "manifest"
    catalog_path: Path = PROJECT_ROOT / "config" / "products.real.json"
    screenshot_manifest_path: Path = PROJECT_ROOT / "config" / "screenshots.manifest.json"
    screenshot_root: Path = PROJECT_ROOT
    roi_profiles_path: Path = PROJECT_ROOT / "config" / "roi_profiles.json"
    phrase_sets_path: Path = PROJECT_ROOT / "config" / "phrase_sets.json"
    artifact_root: Path = PROJECT_ROOT / "output" / "artifacts"
    database_url: str = ""
    scheduler_enabled: bool = False
    scan_interval_seconds: int = 3600
    max_concurrency: int = 3
    scan_timeout_seconds: float = 120.0
    tesseract_cmd: str | None = None
    tesseract_languages: str = "eng+deu+ita"
    ocr_scale: int = 3


def load_monitoring_config(
    environ: Mapping[str, str] | None = None,
    *,
    project_root: str | Path | None = None,
) -> MonitoringRuntimeConfig:
    root = Path(project_root or PROJECT_ROOT)
    if environ is None:
        values = _dotenv_values(root / ".env")
        values.update(os.environ)
    else:
        values = dict(environ)

    mode = values.get("MONITORING_MODE", "demo").strip().lower()
    if mode not in {"demo", "real"}:
        raise ValueError("MONITORING_MODE must be demo or real")
    input_mode = values.get("MONITORING_INPUT_MODE", "manifest").strip().lower()
    if input_mode not in {"manifest", "live"}:
        raise ValueError("MONITORING_INPUT_MODE must be manifest or live")

    interval = _positive_int(values, "MONITORING_SCAN_INTERVAL_SECONDS", 3600)
    concurrency = _positive_int(values, "MONITORING_MAX_CONCURRENCY", 3)
    timeout = _positive_float(values, "MONITORING_SCAN_TIMEOUT_SECONDS", 120.0)

    return MonitoringRuntimeConfig(
        mode=mode,  # type: ignore[arg-type]
        input_mode=input_mode,  # type: ignore[arg-type]
        catalog_path=_resolve(root, values.get("MONITORING_CATALOG_PATH", "config/products.real.json"), root),
        screenshot_manifest_path=_resolve(
            root,
            values.get("MONITORING_SCREENSHOT_MANIFEST_PATH", "config/screenshots.manifest.json"),
            root,
        ),
        screenshot_root=_resolve(
            root,
            values.get("MONITORING_SCREENSHOT_ROOT", "."),
            root,
        ),
        roi_profiles_path=_resolve(root, values.get("MONITORING_ROI_PROFILES_PATH", "config/roi_profiles.json"), root),
        phrase_sets_path=_resolve(root, values.get("MONITORING_PHRASE_SETS_PATH", "config/phrase_sets.json"), root),
        artifact_root=_resolve(root, values.get("MONITORING_ARTIFACT_ROOT", "output/artifacts"), root),
        database_url=values.get("MONITORING_DATABASE_URL", "").strip(),
        scheduler_enabled=_as_bool(values.get("MONITORING_SCHEDULER_ENABLED", "false")),
        scan_interval_seconds=interval,
        max_concurrency=concurrency,
        scan_timeout_seconds=timeout,
        tesseract_cmd=values.get("TESSERACT_CMD", "").strip() or None,
        tesseract_languages=values.get("TESSERACT_LANGUAGES", "eng+deu+ita").strip() or "eng+deu+ita",
        ocr_scale=_positive_int(values, "OCR_SCALE", 3),
    )


def validate_real_prerequisites(config: MonitoringRuntimeConfig) -> list[str]:
    if config.mode == "demo":
        return []

    errors: list[str] = []
    if not config.screenshot_root.is_dir():
        errors.append(f"screenshot root is missing: {config.screenshot_root}")
    for label, path in (
        ("catalog", config.catalog_path),
        ("screenshot manifest", config.screenshot_manifest_path),
        ("ROI profile", config.roi_profiles_path),
        ("phrase set", config.phrase_sets_path),
    ):
        if not path.is_file():
            errors.append(f"{label} file is missing: {path}")

    if not config.database_url:
        errors.append("database URL is required in real mode")

    executable = config.tesseract_cmd or shutil.which("tesseract")
    if not executable or (config.tesseract_cmd and not Path(executable).is_file()):
        errors.append("Tesseract executable is not available")
    else:
        errors.extend(_validate_tesseract_languages(executable, config.tesseract_languages))
    return errors


def monitoring_status(config: MonitoringRuntimeConfig, *, scheduler_running: bool = False) -> dict:
    missing = validate_real_prerequisites(config)
    return {
        "mode": config.mode,
        "input_mode": config.input_mode,
        "scheduler_enabled": config.scheduler_enabled,
        "scheduler_running": scheduler_running,
        "ocr": {"engine": "tesseract", "languages": config.tesseract_languages},
        "preflight": {"ready": not missing, "missing": missing},
    }


def _validate_tesseract_languages(executable: str, requested: str) -> list[str]:
    try:
        import pytesseract

        previous = pytesseract.pytesseract.tesseract_cmd
        pytesseract.pytesseract.tesseract_cmd = executable
        try:
            available = set(pytesseract.get_languages(config=""))
        finally:
            pytesseract.pytesseract.tesseract_cmd = previous
    except Exception:
        return ["Tesseract language data could not be inspected"]

    missing = [lang for lang in requested.split("+") if lang and lang not in available]
    return [f"Tesseract language data is missing: {', '.join(missing)}"] if missing else []


def _resolve(root: Path, value: str, _project_root: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def _positive_int(values: Mapping[str, str], key: str, default: int) -> int:
    value = int(values.get(key, str(default)))
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _positive_float(values: Mapping[str, str], key: str, default: float) -> float:
    value = float(values.get(key, str(default)))
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _dotenv_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result
