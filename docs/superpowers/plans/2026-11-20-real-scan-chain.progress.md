# SDD ledger — plan: docs/superpowers/plans/2026-11-20-real-scan-chain.md
Pre-flight: Git metadata unavailable in this workspace; execution will use file-based progress and no commits.
Pre-flight interface: Task 1 config feeds Task 3 bootstrap; Task 2 observation factory feeds Task 3 scanner wiring; Task 4 repositories feed Task 3/5 runtime; Task 5 lifecycle triggers Task 6 retention.
Ruling: Keep Demo as default and do not install Kafka/Feishu; the approved MVP scope explicitly excludes them.
Ruling: Real mode remains opt-in and must fail preflight clearly when Tesseract or required real config is absent; this prevents false healthy results.

Ruling: Reordered the Real path around existing crawler screenshot manifests; this avoids duplicate crawling and validates OCR/alert behavior from already authorized artifacts. Cost if wrong: manifest format may need an adapter when the upstream crawler export is finalized.
Plan revised: Task 2 adds JsonScreenshotManifestSource/CrawlerScreenshotScanner; Task 3 selects manifest vs live input mode; Git/worktree steps remain excluded.
Task 1: complete (file-based; tests: uv run --cache-dir .uv-cache python -m unittest tests.test_runtime_config -v -> 4/4 passed; Demo does not require Real prerequisites).
Task 2: complete (file-based; tests: crawler screenshot source + real observation + Playwright scanner -> 15/15 passed).
Task 3: complete (file-based; tests: tests.test_real_bootstrap -> 4/4 passed; manifest mode avoids browser creation).
Task 4: partial (file-based; SQLite contract health and Artifact repository -> 3/3 passed; MySQL runtime wiring remains pending).
Task 5: partial (file-based; lifecycle tests -> 3/3 passed; scheduler wiring is available through bootstrap lifespan, but production scheduler acceptance remains pending).
Task 6: existing retention behavior remains green; full persistence lifecycle integration is pending.
Verification: full suite 108/108 passed; uv lock --check passed; compileall passed with project-local PYTHONPYCACHEPREFIX because shared cache is permission restricted.
Final review: self-review (fresh reviewer was interrupted after no result). Key remaining gaps: Tesseract system binary, real catalog/manifest/ROI/phrase files, MySQL repository wiring into bootstrap, and full evidence lifecycle integration. No claims of real-site readiness made.
