from __future__ import annotations

import asyncio
import inspect
from contextlib import suppress
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.browser.browser_manager import BrowserManager
from app.monitoring.adapters.roi import RoiCropper, RoiError, has_image_content
from app.monitoring.adapters.ocr_tesseract import OcrError
from app.monitoring.application.ports import ArtifactMetadata, ArtifactStore
from app.monitoring.application.real_observation import RealObservationFactory, find_usable_add_to_cart_button
from app.monitoring.config.markets import AMAZON_LOCALES, resolve_target_postal_code
from app.monitoring.config.postal_codes import postal_matches, postal_values_equal
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
    SCREENSHOT_BLANK = "SCREENSHOT_BLANK"
    ROI_BLANK = "ROI_BLANK"
    ARTIFACT_SAVE_FAILED = "ARTIFACT_SAVE_FAILED"
    ROI_FAILED = "ROI_FAILED"
    OCR_NOT_CONFIGURED = "OCR_NOT_CONFIGURED"
    POSTAL_CODE_REQUIRED = "POSTAL_CODE_REQUIRED"
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
        delivery_timeout_ms: int = 20_000,
    ):
        self.browser_manager = browser_manager or BrowserManager()
        self.platform_registry = platform_registry
        self.observation_factory = observation_factory
        self.artifact_store = artifact_store
        self.roi_profile_loader = roi_profile_loader
        self.roi_cropper = roi_cropper or RoiCropper()
        self.timeout_ms = timeout_ms
        self.delivery_diagnostic_root = Path(delivery_diagnostic_root)
        self.delivery_timeout_ms = delivery_timeout_ms

    async def scan(self, product: Product) -> ScanObservation:
        # 并发扫描共用扫描器实例，诊断随单次调用传递，避免混入其他商品的记录。
        cookie_diagnostics: list[tuple[bool, str]] = []
        observation = await self._scan(product, cookie_diagnostics)
        if any(abnormal for abnormal, _ in cookie_diagnostics):
            diagnostics = "；".join(message for _, message in cookie_diagnostics)
            if observation.status == ProductScanStatus.TECHNICAL_FAILURE:
                parts = (diagnostics, observation.error_message)
            else:
                parts = (observation.error_message, diagnostics)
            observation.error_message = "；".join(part for part in parts if part)
        return observation

    async def _scan(self, product: Product, cookie_diagnostics: list[tuple[bool, str]]) -> ScanObservation:
        started_at = datetime.now(timezone.utc)
        session = None
        requires_delivery = product.platform == "amazon"
        target_postal_code = self._resolve_postal_code(product) if requires_delivery else ""
        if requires_delivery and not target_postal_code:
            return self._failure(
                ScanErrorCode.POSTAL_CODE_REQUIRED,
                "缺少有效的 Amazon 站点，无法确定配送邮编",
                started_at,
            )

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
                    locale=AMAZON_LOCALES[product.country.upper()] if requires_delivery and product.country.upper() in AMAZON_LOCALES else profile.browser.get("locale", "en-US"),
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
                continue_selectors = location.get("continue_selectors", [])
                await self._click_continue_shopping(page, continue_selectors)

                stage = "reject optional cookies"
                reject_selector = getattr(profile, "cookies", {}).get("reject")
                if reject_selector:
                    cookie_diagnostics.append(
                        await self._reject_optional_cookies(page, reject_selector, "首次访问")
                    )
                    if self._is_marketplace_home(page.url, product.url):
                        stage = "reopen product from marketplace homepage"
                        await self._reopen_product(page, product.url)
                        stage = "continue shopping after reopening product"
                        await self._click_continue_shopping(page, continue_selectors)
            except Exception as exc:
                evidence = await self._capture_ready_failure(page, product, started_at)
                return self._failure(
                    ScanErrorCode.READY_SELECTOR_FAILED,
                    f"{stage} failed: {exc}",
                    started_at,
                    full_screenshot_path=evidence,
                )

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
                    cookie_diagnostics.append(
                        await self._reject_optional_cookies(page, reject_selector, "商品页就绪后")
                    )
            except Exception as exc:
                evidence = await self._capture_ready_failure(page, product, started_at)
                return self._failure(
                    ScanErrorCode.READY_SELECTOR_FAILED,
                    f"reject optional cookies on product page failed: {exc}",
                    started_at,
                    full_screenshot_path=evidence,
                )

            # The delivery dialog can be slow or stuck. Bound it so a blocked
            # postal-code setup cannot stall the whole scan.
            if requires_delivery:
                try:
                    delivery_error = await asyncio.wait_for(
                        self._configure_delivery(page, profile, product, target_postal_code),
                        timeout=self.delivery_timeout_ms / 1000,
                    ) or ""
                except asyncio.TimeoutError:
                    delivery_error = (
                        f"delivery setup timed out after {self.delivery_timeout_ms}ms"
                    )
                except Exception as exc:
                    delivery_error = f"delivery setup failed: {type(exc).__name__}: {exc}"
                if delivery_error:
                    with suppress(OSError, PlaywrightError, TimeoutError):
                        directory = self._delivery_diagnostic_dir(product)
                        directory.mkdir(parents=True, exist_ok=True)
                        await page.screenshot(
                            path=str(directory / "delivery_failed.png"),
                            full_page=False,
                            timeout=min(self.timeout_ms, 5_000),
                        )
                    await self._close_delivery_dialog(page)
                    evidence = await self._capture_ready_failure(page, product, started_at)
                    return self._failure(
                        ScanErrorCode.DELIVERY_REGION_UNVERIFIED, delivery_error, started_at,
                        full_screenshot_path=evidence,
                    )

            screenshot = None
            observation_image = None
            dom_evidence = None
            evidence_error = None
            for attempt in range(2):
                if requires_delivery or attempt:
                    try:
                        for selector in selectors:
                            await page.wait_for_selector(
                                selector, state="visible", timeout=min(self.timeout_ms, 10_000)
                            )
                    except (PlaywrightTimeoutError, TimeoutError) as exc:
                        evidence = await self._capture_ready_failure(page, product, started_at)
                        return self._failure(
                            ScanErrorCode.READY_SELECTOR_MISSING,
                            f"product page not ready before evidence capture: {exc}",
                            started_at, full_screenshot_path=evidence,
                        )

                try:
                    dom_evidence = await find_usable_add_to_cart_button(page)
                    screenshot = await page.screenshot(full_page=True)
                except Exception as exc:
                    return self._failure(ScanErrorCode.SCREENSHOT_FAILED, str(exc), started_at)

                observation_image = None
                if not has_image_content(screenshot, below_header=True):
                    evidence_error = (ScanErrorCode.SCREENSHOT_BLANK, "product screenshot is blank below the header")
                    continue

                if self.roi_profile_loader is not None:
                    try:
                        roi_profile = self.roi_profile_loader.load(product.roi_profile_id)
                        if inspect.isawaitable(roi_profile):
                            roi_profile = await roi_profile
                        observation_image = await self._crop_product_roi(
                            product, page, screenshot, roi_profile, dom_evidence=dom_evidence
                        )
                    except Exception as exc:
                        evidence_error = (ScanErrorCode.ROI_FAILED, str(exc))
                        continue
                    if not has_image_content(observation_image):
                        evidence_error = (ScanErrorCode.ROI_BLANK, "product ROI is blank")
                        continue
                evidence_error = None
                break

            full_artifact_path = None
            roi_artifact_path = None
            if self.artifact_store is not None:
                try:
                    full_artifact_path = await self._save_evidence(screenshot, product, started_at, "full")
                    if observation_image is not None:
                        roi_artifact_path = await self._save_evidence(observation_image, product, started_at, "roi")
                except Exception as exc:
                    return self._failure(
                        ScanErrorCode.ARTIFACT_SAVE_FAILED, str(exc), started_at,
                        full_screenshot_path=full_artifact_path,
                    )

            if evidence_error is not None:
                code, message = evidence_error
                return self._failure(
                    code, message, started_at,
                    full_screenshot_path=full_artifact_path, roi_screenshot_path=roi_artifact_path,
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
                image = observation_image if observation_image is not None else screenshot
                if isinstance(self.observation_factory, RealObservationFactory):
                    observation = self.observation_factory(product, page, image, dom_evidence=dom_evidence)
                else:
                    observation = self.observation_factory(product, page, image)
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

            observation = self._with_timestamps(
                observation,
                started_at,
                full_screenshot_path=full_artifact_path,
                roi_screenshot_path=roi_artifact_path,
            )
            return observation
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

    async def _save_evidence(self, image, product, started_at, kind):
        reference = await self.artifact_store.save(image, ArtifactMetadata(
            country=product.country, platform=product.platform, sku=product.sku,
            artifact_type=kind, captured_at=started_at,
        ))
        return reference.path

    async def _crop_product_roi(self, product, page, screenshot, profile, *, dom_evidence=None):
        if product.platform == "amazon":
            _, button = dom_evidence if dom_evidence is not None else await find_usable_add_to_cart_button(page)
            if button is not None:
                try:
                    return await button.screenshot(timeout=min(self.timeout_ms, 3_000))
                except PlaywrightError as exc:
                    raise RoiError("validated add-to-cart button could not be captured") from exc
        return await self.roi_cropper.crop(screenshot, profile, page=page)

    async def _click_continue_shopping(self, page, selectors: list[str]) -> None:
        for selector in selectors:
            button = page.locator(selector).first
            if await button.count() and await button.is_visible():
                await button.click(timeout=min(self.timeout_ms, 5_000))
                return

    async def _reject_optional_cookies(self, page, selector: str, stage: str) -> tuple[bool, str]:
        reject = page.locator(selector).first
        # 只记录可定位页面的地址，避免查询参数或登录凭据进入扫描结果。
        url = urlsplit(page.url)
        address = url._replace(netloc=url.netloc.rsplit("@", 1)[-1], query="", fragment="").geturl()
        # 6 秒覆盖常见的 3–5 秒延迟渲染，按钮一旦可见即可点击。
        try:
            await reject.wait_for(state="visible", timeout=min(self.timeout_ms, 6_000))
        except PlaywrightTimeoutError:
            return True, f"{stage}：Cookie 面板未出现（{address}）"
        # 沿用点击和关闭各 5 秒的上限，防止弹窗交互阻塞商品扫描。
        timeout = min(self.timeout_ms, 5_000)
        await reject.click(timeout=timeout)
        try:
            await reject.wait_for(state="hidden", timeout=timeout)
        except PlaywrightTimeoutError:
            return True, f"{stage}：Cookie 拒绝按钮点击后未消失（{address}）"
        return False, f"{stage}：Cookie 面板已拒绝（{address}）"

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
            navigation_interrupted = (
                "interrupted by another navigation" in str(exc)
                or "net::ERR_ABORTED" in str(exc)
            )
            if not navigation_interrupted or not self._is_marketplace_home(page.url, url):
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

    @staticmethod
    def _resolve_postal_code(product: Product) -> str:
        return resolve_target_postal_code(product.country)

    def _delivery_diagnostic_dir(self, product: Product) -> Path:
        return self.delivery_diagnostic_root / product.country / product.platform / product.id

    async def _configure_delivery(self, page, profile, product, postal_code: str) -> str | None:
        location = getattr(profile, "location", {})
        diagnostic_dir = self._delivery_diagnostic_dir(product)
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        details = {"delivery_text_before": "", "postal_input_found": False, "postal_input_value": "", "submit_succeeded": False, "confirm_button_found": False, "delivery_text_after": "", "stage": "start"}
        try:
            result = page.locator(location.get("result", "#glow-ingress-block")).first
            if await result.count():
                details["delivery_text_before"] = (await result.inner_text()).strip()
            await page.screenshot(path=str(diagnostic_dir / "delivery_before.png"), full_page=False)
            trigger = page.locator(location.get("trigger", "#nav-global-location-popover-link")).first
            details["stage"] = "click trigger"
            await trigger.click(timeout=min(self.timeout_ms, 10_000))
            details["stage"] = "wait for postal input"
            primary_field = page.locator(location.get("postal_input", "#GLUXZipUpdateInput")).first
            # 弹窗内容可能稍晚渲染，邮编框最多占用配送总预算 20 秒中的 8 秒。
            # 主选择器每次最多等 100 毫秒，让不同布局的兜底控件也能及时被发现。
            try:
                async with asyncio.timeout(min(self.timeout_ms, 8_000) / 1000):
                    while True:
                        try:
                            await primary_field.wait_for(state="visible", timeout=100)
                            field = primary_field
                            break
                        except PlaywrightTimeoutError:
                            field = await self._find_delivery_postal_input(page)
                            if await field.is_visible():
                                break
            except TimeoutError:
                await page.screenshot(path=str(diagnostic_dir / "delivery_input_missing.png"), full_page=False)
                await self._close_delivery_dialog(page)
                return self._delivery_error(details, diagnostic_dir, "postal input not found or not visible")
            details["postal_input_found"] = True
            await page.screenshot(path=str(diagnostic_dir / "delivery_dialog.png"), full_page=False)
            details["stage"] = "fill postal code"
            input_value = await field.input_value()
            if not postal_values_equal(input_value, postal_code):
                # 保留原有 5 秒清空和 8 秒输入上限，已有正确值时避开可能阻塞的输入校验。
                try:
                    await field.click(timeout=5000)
                    await field.fill("", timeout=5000)
                except Exception:
                    pass
                await field.type(postal_code, delay=60, timeout=8000)
                input_value = await field.input_value()
            details["postal_input_value"] = input_value
            if not postal_values_equal(input_value, postal_code):
                return self._delivery_error(
                    details,
                    diagnostic_dir,
                    f"postal input differs from requested value: expected={postal_code!r}, actual={input_value!r}",
                )
            details["stage"] = "click submit"
            submit = page.locator(location.get("submit", "#GLUXZipUpdate .a-button-input")).first
            if not await submit.count() or not await submit.is_visible():
                submit = await self._find_delivery_submit(page)
            if await submit.count() and await submit.is_visible():
                await submit.click(timeout=8000)
                details["submit_succeeded"] = True
                details["stage"] = "wait confirm"
            else:
                # 输入邮编后亚马逊会实时校验，「Bestätigen」可能已经消失，
                # 此时直接进入确认阶段点击「Fertig」。
                details["stage"] = "confirm only"

            # 亚马逊是两段式弹窗：填邮编并确认后，才出现「Fertig」按钮，
            # 点击它才会真正应用新的配送地。
            confirm = page.locator(location.get("confirm", "#GLUXConfirmClose")).first
            try:
                await confirm.wait_for(state="visible", timeout=6000)
            except Exception:
                pass
            if not (await confirm.count()) or not (await confirm.is_visible()):
                confirm = await self._find_delivery_confirm(page)
            details["confirm_button_found"] = bool(
                await confirm.count() and await confirm.is_visible()
            )
            if details["confirm_button_found"]:
                await confirm.click(timeout=8000)
            elif not details["submit_succeeded"]:
                await self._close_delivery_dialog(page)
                return self._delivery_error(details, diagnostic_dir, "delivery submit control not found")
            await self._close_delivery_dialog(page)
            details["stage"] = "read delivery header"
            # 沿用 5 秒的可见等待上限，给页头重绘留出时间，同时受扫描超时约束。
            try:
                await result.wait_for(state="visible", timeout=min(self.timeout_ms, 5_000))
            except PlaywrightTimeoutError:
                await page.screenshot(path=str(diagnostic_dir / "delivery_after_submit.png"), full_page=False)
                return self._delivery_error(details, diagnostic_dir, "页头配送栏未显示")
            # 沿用 2 秒的读取上限，避免页头在读回时重新渲染导致长时间阻塞。
            details["delivery_text_after"] = (await result.inner_text(timeout=2_000)).strip()
            await page.screenshot(path=str(diagnostic_dir / "delivery_after_submit.png"), full_page=False)
            if not postal_matches(details["delivery_text_after"], postal_code):
                return self._delivery_error(details, diagnostic_dir, f"页头仍显示：{details['delivery_text_after']}")
            return None
        except Exception as exc:
            return self._delivery_error(details, diagnostic_dir, f"delivery region setup failed: {type(exc).__name__}")

    @staticmethod
    def _delivery_error(details: dict, diagnostic_dir: Path, reason: str) -> str:
        safe = "; ".join(f"{key}={value}" for key, value in details.items())
        return f"{reason}; {safe}; diagnostics={diagnostic_dir}"

    @staticmethod
    async def _close_delivery_dialog(page) -> None:
        """关闭配送弹窗。

        弹窗残留会遮挡加购按钮，导致后续 DOM 按钮探测失败。配送设置属于
        尽力而为，失败时必须把弹窗收干净，让按钮判定照常进行。
        """
        for selector in (
            "button:has-text('Fertig')",
            "a:has-text('Fertig')",
            "#GLUXConfirmClose",
            "button[aria-label='Close']",
            "[role='dialog'] button:has-text('×')",
            "[role='dialog'] [aria-label='Close']",
        ):
            try:
                item = page.locator(selector).first
                if await item.count() and await item.is_visible():
                    await item.click(timeout=3000)
                    await page.wait_for_timeout(800)
                    return
            except Exception:
                continue
        # 兜底：按 Escape 关闭弹窗
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)
        except Exception:
            pass

    @staticmethod
    async def _find_delivery_postal_input(page):
        """在配送弹窗中定位邮编输入框。

        优先按属性关键字（postal/postcode/postleitzahl/plz/zip）匹配；
        亚马逊新版弹窗的输入框是没有任何属性的裸 input，因此还需要按
        弹窗结构兜底：取弹窗内第一个可见的文本输入框。
        """
        scope = page.locator('[role="dialog"]').last
        has_dialog = bool(await scope.count())
        if not has_dialog:
            scope = page
        candidates = scope.locator("input, textarea, [role='textbox'], [role='combobox']")
        total = await candidates.count()
        for index in range(total):
            item = candidates.nth(index)
            haystack = " ".join([
                (await item.get_attribute(name) or "")
                for name in ("id", "name", "placeholder", "aria-label", "autocomplete")
            ]).lower()
            if (
                any(term in haystack for term in ("postal", "postcode", "postleitzahl", "plz", "zip", "postnummer", "codice postale", "kod pocztowy"))
                and await item.is_visible()
            ):
                return item

        # 弹窗尚未出现时，页头搜索框可能已经可见，不能用于结构兜底。
        if not has_dialog:
            return page.locator("#__delivery_postal_not_found__")

        # 结构性兜底：弹窗内第一个可见的文本输入框。
        for index in range(total):
            item = candidates.nth(index)
            try:
                input_type = (await item.get_attribute("type") or "text").lower()
            except Exception:
                input_type = "text"
            if input_type in {"hidden", "submit", "button", "checkbox", "radio"}:
                continue
            try:
                if await item.is_visible():
                    return item
            except Exception:
                continue
        return page.locator("#__delivery_postal_not_found__")

    @staticmethod
    async def _find_delivery_submit(page):
        scope = page.locator('[role="dialog"]').last
        if not await scope.count():
            scope = page
        buttons = scope.locator("button, input[type='submit'], [role='button']")
        for index in range(await buttons.count()):
            item = buttons.nth(index)
            text = ((await item.inner_text()) + " " + (await item.get_attribute("aria-label") or "")).lower()
            if any(term in text for term in ("apply", "submit", "weiter", "bestätigen", "confirm", "speichern", "toepassen", "appliquer", "applica", "aplicar", "använd", "zastosuj")):
                return item
        return page.locator("#__delivery_submit_not_found__")

    @staticmethod
    async def _find_delivery_confirm(page):
        """定位「Fertig」确认按钮（亚马逊两段式弹窗的第二步）。

        注意不能用 `text=Fertig`：页面上存在多个匹配，其中第一个可能不可见，
        点击会一直等到超时。这里逐个候选检查可见性再返回。
        """
        for selector in (
            "button:has-text('Fertig')",
            "a:has-text('Fertig')",
            "#GLUXConfirmClose",
            "button:has-text('Done')",
            "button:has-text('Appliquer')",
            "button:has-text('Applica')",
            "button:text-is('Gereed')",
            "button:text-is('Terminé')",
            "button:text-is('Listo')",
            "button:text-is('Klar')",
            "button:text-is('Gotowe')",
        ):
            try:
                candidates = page.locator(selector)
                total = await candidates.count()
                for index in range(total):
                    item = candidates.nth(index)
                    if await item.is_visible():
                        return item
            except Exception:
                continue
        return page.locator("#__delivery_confirm_not_found__")

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
