import tempfile
import unittest
from pathlib import Path

from app.monitoring.runtime_config import (
    MonitoringRuntimeConfig,
    load_monitoring_config,
    validate_real_prerequisites,
)


class RuntimeConfigTests(unittest.TestCase):
    def test_demo_mode_does_not_require_real_paths_or_database(self):
        config = load_monitoring_config({"MONITORING_MODE": "demo"})

        self.assertEqual(config.mode, "demo")
        self.assertEqual(validate_real_prerequisites(config), [])

    def test_real_mode_requires_catalog_roi_phrase_and_database_configuration(self):
        config = load_monitoring_config(
            {
                "MONITORING_MODE": "real",
                "MONITORING_CATALOG_PATH": "missing-products.json",
                "MONITORING_ROI_PROFILES_PATH": "missing-roi.json",
                "MONITORING_PHRASE_SETS_PATH": "missing-phrases.json",
            }
        )

        errors = validate_real_prerequisites(config)

        self.assertTrue(any("catalog" in error for error in errors))
        self.assertTrue(any("ROI" in error for error in errors))
        self.assertTrue(any("phrase" in error for error in errors))
        self.assertTrue(any("database" in error for error in errors))

    def test_default_interval_is_3600_and_concurrency_is_3(self):
        config = load_monitoring_config({})

        self.assertEqual(config.scan_interval_seconds, 3600)
        self.assertEqual(config.max_concurrency, 3)

    def test_path_values_are_resolved_relative_to_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_monitoring_config(
                {"MONITORING_ARTIFACT_ROOT": "artifacts"}, project_root=root
            )

        self.assertEqual(config.artifact_root, root / "artifacts")

    def test_default_loader_reads_project_dotenv_for_tesseract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("TESSERACT_CMD=C:/tools/tesseract.exe\n", encoding="utf-8")
            config = load_monitoring_config(project_root=root)

        self.assertEqual(config.tesseract_cmd, "C:/tools/tesseract.exe")


if __name__ == "__main__":
    unittest.main()
