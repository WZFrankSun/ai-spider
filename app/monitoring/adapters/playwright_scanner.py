from __future__ import annotations

import inspect
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.browser.browser_manager import BrowserManager
from app.monitoring.adapters.roi import RoiCropper, RoiError
from app.monitoring.adapters.ocr_tesseract import OcrError
from app.monitoring.application.ports import ArtifactMetadata, ArtifactStore
from app.monitoring.application.real_observation import find_usable_add_to_cart_button
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation
from app.platforms.registry import PlatformRegistry


class ScanErrorCode(str, Enum):
    PLATFORM_NOT_FOUND = "PLATFORM_NOT_FOUND"
    BROWSER_START_FAILED = "BROWSER_START_FAILED"
    SESSION_CREATE_FAILED = "SESSION_CREATE_FAILED"
    PAGE_NOT_AVAILABLE = "PAGE_NOT_AVAILABLE"
    NAVIGATION_TIMEOUT = "NAVIGATION_TIMEOUT"
    NAVIGATION_FAILED = "NAVIGATION_FAILED"
    READY_SELECTOR_MISSING = "READY_SELECTOR_MISSING"
    READY_SELECTOR_FAILED = "READY_SELECTOR_FAILED"
    SCREENSHOT_FAILED = "SCREENSHOT_FAILED"
    ARTIFACT_SAVE_FAILED = "ARTIFACT_SAVE_FAILED"
    ROI_FAILED = "ROI_FAILED"
    OCR_NOT_CONFIGURED = "OCR_NOT_CONFIGURED"
    DELIVERY_REGION_UNVERIFIED = "DELIVERY_REGION_UNVERIFIED"
    OBSERVATION_BUILD_FAILED = "OBSERVATION_BUILD_FAILED"
    UNEXPECTED_SCAN_ERROR = "UNEXPECTED_SCAN_ERROR"


ObservationFactory = Callable[
    [Product, object, bytes], ScanObservation | Awaitable[ScanObservation]
]


class PlaywrightScanner:
    """执行页面访问阶段，并把浏览器故障转换为领域观察结果。

    OCR 尚未接入时，成功打开页面只返回 `OCR_NOT_CONFIGURED` 技术故障，
    避免把“页面可访问”误判为“已识别到加购入口”。T10 可以通过
    `observation_factory` 注入 OCR 和词库匹配结果。
    """

    def __init__(
        self,
        browser_manager: BrowserManager | None = None,
        platform_registry=PlatformRegistry,
        observation_factory: ObservationFactory | None = None,
        artifact_store: ArtifactStore | None = None,
        roi_profile_loader=None,
        roi_cropper: RoiCropper | None = None,
        timeout_ms: int = 30_000,
        delivery_diagnostic_root: str | Path = "output/delivery-diagnostics",
        delivery_validation_exempt_ids: set[str] | None = None,
    ):
        self.browser_manager = browser_manager or BrowserManager()
        self.platform_registry = platform_registry
        self.observation_factory = observation_factory
        self.artifact_store = artifact_store
        self.roi_profile_loader = roi_profile_loader
        self.roi_cropper = roi_cropper or RoiCropper()
        self.timeout_ms = timeout_ms
        self.delivery_diagnostic_root = Path(delivery_diagnostic_root)
        self.delivery_validation_exempt_ids = delivery_validation_exempt_ids or set()

    async def scan(self, product: Product) -> ScanObservation:
        started_at = datetime.now(timezone.utc)
        session = None

        try:
            try:
                profile = self.platform_registry.load(product.platform)
            except KeyError as exc:
                return self._failure(
                    ScanErrorCode.PLATFORM_NOT_FOUND,
                    str(exc),
                    started_at,
                )

            try:
                await self.browser_manager.start()
            except Exception as exc:
                return self._failure(
                    ScanErrorCode.BROWSER_START_FAILED,
                    str(exc),
                    started_at,
                )

            try:
                session = await self.browser_manager.create_session(
                    viewport=profile.browser.get("viewport"),
                    locale=profile.browser.get("locale") or _locale_for(product.country),
                )
            except Exception as exc:
                return self._failure(
                    ScanErrorCode.SESSION_CREATE_FAILED,
                    str(exc),
                    started_at,
                )

            page = getattr(session, "page", None)
            if page is None:
                return self._failure(
                    ScanErrorCode.PAGE_NOT_AVAILABLE,
                    "browser session has no page",
                    started_at,
                )

            try:
                await page.goto(
                    product.url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )
            except (PlaywrightTimeoutError, TimeoutError) as exc:
                return self._failure(
                    ScanErrorCode.NAVIGATION_TIMEOUT,
                    str(exc),
                    started_at,
                )
            except Exception as exc:
                return self._failure(
                    ScanErrorCode.NAVIGATION_FAILED,
                    str(exc),
                    started_at,
                )

            stage = "continue shopping"
            try:
                location = getattr(profile, "location", {})
                for selector in location.get("continue_selectors", []):
                    button = page.locator(selector).first
                    if await button.count() and await button.is_visible():
                        await button.click(timeout=min(self.timeout_ms, 5_000))
                        break

                stage = "reject optional cookies"
                reject_selector = getattr(profile, "cookies", {}).get("reject")
                if reject_selector:
                    await self._reject_optional_cookies(page, reject_selector)
                    if self._is_marketplace_home(page.url, product.url):
                        stage = "reopen product from marketplace homepage"
                        await self._reopen_product(page, product.url)
            except Exception as exc:
                evidence = await self._capture_ready_failure(page, product, started_at)
                return self._failure(
                    ScanErrorCode.READY_SELECTOR_FAILED,
                    f"{stage} failed: {exc}",
                    started_at,
                    full_screenshot_path=evidence,
                )

            # Delivery setup and postal-code validation are temporarily disabled.

            try:
                selectors = profile.resolve_ready_selectors(product.url)
            except Exception as exc:
                return self._failure(
                    ScanErrorCode.READY_SELECTOR_FAILED,
                    str(exc),
                    started_at,
                )

            for selector in selectors:
                try:
                    await page.wait_for_selector(
                        selector,
                        state="attached",
                        timeout=min(self.timeout_ms, 10_000),
                    )
                except (PlaywrightTimeoutError, TimeoutError) as exc:
                    evidence = await self._capture_ready_failure(page, product, started_at)
                    return self._failure(
                        ScanErrorCode.READY_SELECTOR_MISSING,
                        f"required selector not found: {selector}; {exc}",
                        started_at,
                        full_screenshot_path=evidence,
                    )
                except Exception as exc:
                    return self._failure(
                        ScanErrorCode.READY_SELECTOR_FAILED,
                        f"selector failed: {selector}; {exc}",
                        started_at,
                    )

            try:
                if reject_selector:
                    await self._reject_optional_cookies(page, reject_selector)
            except Exception as exc:
                evidence = await self._capture_ready_failure(page, product, started_at)
                return self._failure(
                    ScanErrorCode.READY_SELECTOR_FAILED,
                    f"reject optional cookies on product page failed: {exc}",
                    started_at,
                    full_screenshot_path=evidence,
                )

            try:
                screenshot = await page.screenshot(full_page=True)
            except Exception as exc:
                return self._failure(
                    ScanErrorCode.SCREENSHOT_FAILED,
                    str(exc),
                    started_at,
                )

            full_artifact_path = None
            roi_artifact_path = None
            observation_image = screenshot
            if self.artifact_store is not None:
                try:
                    full_ref = await self.artifact_store.save(
                        screenshot,
                        ArtifactMetadata(
                            country=product.country,
                            platform=product.platform,
                            sku=product.sku,
                            artifact_type="full",
                            captured_at=started_at,
                        ),
                    )
                    full_artifact_path = full_ref.path
                except Exception as exc:
                    return self._failure(
                        ScanErrorCode.ARTIFACT_SAVE_FAILED,
                        str(exc),
                        started_at,
                    )

            if self.roi_profile_loader is not None:
                try:
                    profile = self.roi_profile_loader.load(product.roi_profile_id)
                    if inspect.isawaitable(profile):
                        profile = await profile
                    observation_image = await self._crop_product_roi(product, page, screenshot, profile)
                    if self.artifact_store is not None:
                        roi_ref = await self.artifact_store.save(
                            observation_image,
                            ArtifactMetadata(
                                country=product.country,
                                platform=product.platform,
                                sku=product.sku,
                                artifact_type="roi",
                                captured_at=started_at,
                            ),
                        )
                        roi_artifact_path = roi_ref.path
                except (RoiError, OSError, ValueError) as exc:
                    return self._failure(
                        ScanErrorCode.ROI_FAILED,
                        str(exc),
                        started_at,
                        full_screenshot_path=full_artifact_path,
                    )
                except Exception as exc:
                    return self._failure(
                        ScanErrorCode.ROI_FAILED,
                        str(exc),
                        started_at,
                        full_screenshot_path=full_artifact_path,
                    )

            if self.observation_factory is None:
                return self._failure(
                    ScanErrorCode.OCR_NOT_CONFIGURED,
                    "page scan succeeded but OCR observation factory is not configured",
                    started_at,
                    full_screenshot_path=full_artifact_path,
                    roi_screenshot_path=roi_artifact_path,
                )

            try:
                observation = self.observation_factory(product, page, observation_image)
                if inspect.isawaitable(observation):
                    observation = await observation
                if not isinstance(observation, ScanObservation):
                    raise TypeError("observation_factory must return ScanObservation")
            except OcrError as exc:
                return self._failure(
                    exc.code,
                    str(exc),
                    started_at,
                    full_screenshot_path=full_artifact_path,
                    roi_screenshot_path=roi_artifact_path,
                )
            except Exception as exc:
                return self._failure(
                    ScanErrorCode.OBSERVATION_BUILD_FAILED,
                    str(exc),
                    started_at,
                    full_screenshot_path=full_artifact_path,
                    roi_screenshot_path=roi_artifact_path,
                )

            return self._with_timestamps(
                observation,
                started_at,
                full_screenshot_path=full_artifact_path,
                roi_screenshot_path=roi_artifact_path,
            )
        except Exception as exc:
            return self._failure(
                ScanErrorCode.UNEXPECTED_SCAN_ERROR,
                str(exc),
                started_at,
            )
        finally:
            if session is not None:
                session_id = getattr(session, "session_id", None)
                if session_id is not None:
                    try:
                        await self.browser_manager.close_session(session_id)
                    except Exception:
                        # A cleanup error must not hide the scan observation.
                        pass

    async def _crop_product_roi(self, product, page, screenshot, profile):
        if product.platform == "amazon":
            _, button = await find_usable_add_to_cart_button(page)
            if button is not None:
                try:
                    return await button.screenshot(timeout=min(self.timeout_ms, 3_000))
                except PlaywrightError:
                    # The button may disappear after the page updates.
                    pass
        return await self.roi_cropper.crop(screenshot, profile, page=page)

    async def _reject_optional_cookies(self, page, selector: str) -> None:
        reject = page.locator(selector).first
        try:
            await reject.wait_for(state="visible", timeout=min(self.timeout_ms, 2_000))
        except PlaywrightTimeoutError:
            return
        timeout = min(self.timeout_ms, 5_000)
        await reject.click(timeout=timeout)
        await reject.wait_for(state="hidden", timeout=timeout)

    @staticmethod
    def _is_marketplace_home(current: str, target: str) -> bool:
        observed = urlsplit(current)
        requested = urlsplit(target)
        return (
            observed.netloc == requested.netloc
            and observed.path in ("", "/")
            and requested.path not in ("", "/")
        )

    async def _reopen_product(self, page, url: str) -> None:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        except PlaywrightError as exc:
            if "interrupted by another navigation" not in str(exc) or not self._is_marketplace_home(page.url, url):
                raise
            await page.wait_for_load_state("domcontentloaded", timeout=min(self.timeout_ms, 5_000))
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)

    async def _capture_ready_failure(self, page, product: Product, started_at: datetime) -> str | None:
        if self.artifact_store is None:
            return None
        try:
            screenshot = await page.screenshot(timeout=3_000)
            ref = await self.artifact_store.save(
                screenshot,
                ArtifactMetadata(
                    country=product.country,
                    platform=product.platform,
                    sku=product.sku,
                    artifact_type="full",
                    captured_at=started_at,
                ),
            )
            return ref.path
        except Exception:
            # Screenshot failure must not mask the original page validation error.
            return None

    async def _configure_delivery(self, page, profile, product) -> str | None:
        delivery = getattr(profile, "delivery", {})
        location = getattr(profile, "location", {})
        postal_code = str(delivery.get("postal_code", "")).strip()
        if not postal_code:
            return None
        diagnostic_dir = self.delivery_diagnostic_root / product.country / product.platform / product.id
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        details = {"delivery_text_before": "", "postal_input_found": False, "postal_input_value": "", "submit_succeeded": False, "confirm_button_found": False, "delivery_text_after": ""}
        try:
            result = page.locator(location.get("result", "#glow-ingress-block"))
            if await result.count():
                details["delivery_text_before"] = (await result.inner_text()).strip()
            await page.screenshot(path=str(diagnostic_dir / "delivery_before.png"), full_page=False)
            trigger = page.locator(location.get("trigger", "#nav-global-location-popover-link"))
            await trigger.click()
            await page.wait_for_timeout(1200)
            await page.screenshot(path=str(diagnostic_dir / "delivery_dialog.png"), full_page=False)
            field = page.locator(location.get("postal_input", "#GLUXZipUpdateInput"))
            if not await field.count() or not await field.is_visible():
                field = await self._find_delivery_postal_input(page)
            details["postal_input_found"] = bool(await field.count() and await field.is_visible())
            if not details["postal_input_found"]:
                return self._delivery_error(details, diagnostic_dir, "postal input not found or not visible")
            await field.fill("")
            await field.fill(postal_code)
            details["postal_input_value"] = await field.input_value()
            submit = page.locator(location.get("submit", "#GLUXZipUpdate .a-button-input"))
            if not await submit.count() or not await submit.is_visible():
                submit = await self._find_delivery_submit(page)
            if not await submit.count() or not await submit.is_visible():
                return self._delivery_error(details, diagnostic_dir, "delivery submit control not found")
            await submit.click()
            details["submit_succeeded"] = True
            confirm = page.locator(location.get("confirm", "#GLUXConfirmClose"))
            details["confirm_button_found"] = bool(await confirm.count() and await confirm.is_visible())
            if details["confirm_button_found"]:
                await confirm.click()
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(diagnostic_dir / "delivery_after_submit.png"), full_page=False)
            await result.wait_for(state="visible", timeout=8000)
            details["delivery_text_after"] = (await result.inner_text()).strip()
            if postal_code not in details["delivery_text_after"]:
                return self._delivery_error(details, diagnostic_dir, "requested delivery postal code not observed")
            return None
        except Exception as exc:
            return self._delivery_error(details, diagnostic_dir, f"delivery region setup failed: {type(exc).__name__}")

    @staticmethod
    def _delivery_error(details: dict, diagnostic_dir: Path, reason: str) -> str:
        safe = "; ".join(f"{key}={value}" for key, value in details.items())
        return f"{reason}; {safe}; diagnostics={diagnostic_dir}"

    @staticmethod
    async def _find_delivery_postal_input(page):
        scope = page.locator('[role="dialog"]').last
        if not await scope.count():
            scope = page
        candidates = scope.locator("input, textarea, [role='textbox'], [role='combobox']")
        for index in range(await candidates.count()):
            item = candidates.nth(index)
            haystack = " ".join(
                (await item.get_attribute(name) or "")
                for name in ("id", "name", "placeholder", "aria-label", "autocomplete")
            ).lower()
            if any(term in haystack for term in ("postal", "postcode", "postleitzahl", "plz", "zip")):
                return item
        return candidates.nth(0) if await candidates.count() == 1 else page.locator("#__delivery_postal_not_found__")

    @staticmethod
    async def _find_delivery_submit(page):
        scope = page.locator('[role="dialog"]').last
        if not await scope.count():
            scope = page
        buttons = scope.locator("button, input[type='submit'], [role='button']")
        for index in range(await buttons.count()):
            item = buttons.nth(index)
            text = ((await item.inner_text()) + " " + (await item.get_attribute("aria-label") or "")).lower()
            if any(term in text for term in ("apply", "submit", "weiter", "bestätigen", "confirm", "speichern")):
                return item
        return page.locator("#__delivery_submit_not_found__")

    @staticmethod
    def _with_timestamps(
        observation: ScanObservation,
        started_at: datetime,
        full_screenshot_path: str | None = None,
        roi_screenshot_path: str | None = None,
    ) -> ScanObservation:
        observation.started_at = started_at
        observation.finished_at = datetime.now(timezone.utc)
        observation.full_screenshot_path = full_screenshot_path
        observation.roi_screenshot_path = roi_screenshot_path
        return observation

    @classmethod
    def _failure(
        cls,
        code: ScanErrorCode,
        message: str,
        started_at: datetime,
        full_screenshot_path: str | None = None,
        roi_screenshot_path: str | None = None,
    ) -> ScanObservation:
        return cls._with_timestamps(
            ScanObservation(
                status=ProductScanStatus.TECHNICAL_FAILURE,
                error_code=code.value if isinstance(code, Enum) else str(code),
                error_message=message,
            ),
            started_at,
            full_screenshot_path=full_screenshot_path,
            roi_screenshot_path=roi_screenshot_path,
        )


def _locale_for(country: str) -> str:
    return {"DE": "de-DE", "IT": "it-IT"}.get(country.upper(), "en-US")
