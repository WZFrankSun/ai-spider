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
        """扫描器。

        两个超时参数的分工：
          timeout_ms (30 秒)         —— 单个操作的通用上限（导航、点击、等选择器）
          delivery_timeout_ms (20 秒) —— 整个配送设置流程的总闸

        配送流程内部还有更细的分段上限（点触发器 10 秒、等邮编框 8 秒、
        点击提交 8 秒、等确认 6 秒、页头回读 5 秒），这些都要在总闸之内，
        否则总闸形同虚设。分段的取舍见各方法内的注释。
        """
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
        """扫描单个商品，返回判定结果。

        这里只做一件事：把 Cookie 处理的诊断信息汇总到结果里。实际的扫描
        逻辑在 _scan 中。

        诊断信息用「参数传递」而不是「实例属性」保存，是因为并发扫描共用
        同一个扫描器实例（HourlyScanRunner 会并发跑多个商品），用实例属性
        会让不同商品的诊断互相污染。

        汇总时的顺序：技术故障时诊断放前面（排查时第一眼就能看到当时
        发生了什么），业务判定成立时诊断放后面（不干扰正常结论）。
        """
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
        """执行一次完整扫描。

        流程：
            1. 查站点默认邮编（亚马逊才需要），缺站点直接终止
            2. 开浏览器、设视口和语言
            3. 导航到商品页
            4. 点「继续购物」→ 重开原链接 → 拒绝 Cookie
            5. 等详情页就绪（商品标题出现）
            6. 配送地设置（填邮编并回读验证）
            7. 截图 + 裁 ROI + OCR
            8. 交由 RealObservationFactory 综合 DOM 与 OCR 证据判定

        每一步失败都返回 technical_failure，并尽量附上证据截图。
        """
        started_at = datetime.now(timezone.utc)
        session = None
        # 只有亚马逊需要设置配送地（其价格、库存、可售状态都随地区变化）。
        requires_delivery = product.platform == "amazon"
        target_postal_code = self._resolve_postal_code(product) if requires_delivery else ""
        if requires_delivery and not target_postal_code:
            # 站点缺失 → 无法确定邮编 → 配送无法设置 → 只能终止。
            # 不允许「跳过配送设置继续扫描」，否则会用随机地区的视角判定。
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

                # 跳转的落点可能是首页或中间页，统一重开原链接再处理商品页弹窗。
                stage = "reopen original product"
                await self._reopen_product(page, product.url)

                stage = "reject optional cookies"
                reject_selector = getattr(profile, "cookies", {}).get("reject")
                if reject_selector:
                    cookie_diagnostics.append(
                        await self._reject_optional_cookies(page, reject_selector, "首次访问")
                    )
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
            #
            # 配送设置失败**必须终止扫描**，不能降级继续。配送地直接决定
            # 加购按钮的判定基准，配送地不对，结论就是错的。
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
        """裁出送入 OCR 的加购区域。

        两种来源，优先级不同：
          1. 有可用按钮时，**直接截按钮本身**（约 200x30）。语义最精确，
             OCR 只需读几个字，不受购买区其他文字干扰。
          2. 找不到可用按钮时，退回裁剪配置的购买区（#rightCol，约 244x240）。
             此时区域内可能有价格提示、愿望单按钮等干扰文字，这也是为什么
             判定要同时看 DOM 和 OCR 两个证据。

        复用 dom_evidence 是为了避免重复探测按钮（探测会做可操作性检查，
        有 2 秒超时开销）。
        """
        if product.platform == "amazon":
            _, button = dom_evidence if dom_evidence is not None else await find_usable_add_to_cart_button(page)
            if button is not None:
                try:
                    return await button.screenshot(timeout=min(self.timeout_ms, 3_000))
                except PlaywrightError as exc:
                    raise RoiError("validated add-to-cart button could not be captured") from exc
        return await self.roi_cropper.crop(screenshot, profile, page=page)

    async def _click_continue_shopping(self, page, selectors: list[str]) -> None:
        """点击「继续购物」拦截页的按钮。

        亚马逊有时会把商品链接重定向到「Continue shopping」中转页，必须点掉它
        才能拿到真实商品页。

        判定方式是从配置里的一组多语言选择器里挨个找，**取第一个存在且可见的**
        就点击并返回。注意这里不做等待：按钮是服务端渲染在 HTML 里的，DOM
        结构一解析完就存在，瞬时查询足够；真正需要等的是 JS 动态插入的弹窗。

        每个站点有各自的文案（德语 Weiter shoppen、意语 Continua lo shopping、
        西语 Seguir comprando 等），全部堆在同一个列表里靠顺序试，所以列表
        越长匹配越慢，新站点漏配文案会导致停在中间页。
        """
        for selector in selectors:
            button = page.locator(selector).first
            if await button.count() and await button.is_visible():
                await button.click(timeout=min(self.timeout_ms, 5_000))
                return

    async def _reject_optional_cookies(self, page, selector: str, stage: str) -> tuple[bool, str]:
        """拒绝 Cookie 同意面板。

        选择「拒绝」而不是「接受」有两个原因：一是拒绝加载的追踪脚本更少，
        页面更接近未登录的裸浏览视角；二是接受 Cookie 可能让亚马逊按偏好把
        商品页重定向到别的站点，扫描目标就偏了。

        等待分三段，各有不同上限：
          1. 等按钮可见，最多 6 秒 —— 首访时面板常在 3–5 秒后才渲染，
             元素一出现就立刻点击，不等满 6 秒；
          2. 点击，最多 5 秒；
          3. 等按钮消失，最多 5 秒 —— 点完必须确认面板真的收掉了，
             否则它会遮挡加购按钮，导致后续按钮探测失败。

        返回 (是否异常, 描述)。等待失败**不终止扫描**：Cookie 面板不是每次
        都出现（会话内已拒绝过、或亚马逊直接不弹），当成致命错误会造成大量
        无谓失败。异常信息会带进最终扫描结果，排查时能直接看到当时状态。
        """
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

    async def _reopen_product(self, page, url: str) -> None:
        """重新访问原始商品链接。

        点掉「继续购物」后的落点只有两种：真实商品页，或同站首页/中间页。
        这里**不做落点判断**，无条件重进 —— 已经在商品页时重进是幂等的
        （最多多花一次网络往返），在首页时重进正是需要的修复。一个动作覆盖
        两种情况，比「判断是不是首页再决定要不要重进」更不容易出错。

        唯一需要特殊处理的是导航中断：亚马逊自己会跳转，导致 Playwright 报
        "interrupted by another navigation" 或 "net::ERR_ABORTED"。这种错误
        只给一次恢复机会（等页面稳定后重试），其他异常照常抛出。
        """
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        except PlaywrightError as exc:
            navigation_interrupted = (
                "interrupted by another navigation" in str(exc)
                or "net::ERR_ABORTED" in str(exc)
            )
            if not navigation_interrupted:
                raise
            # 沿用 5 秒上限让抢占导航先稳定，只给重开一次恢复机会。
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
        """设置配送地并回读验证。

        这一步决定了后续「加购按钮在不在」的判断基准。Playwright 开的是
        全新浏览器上下文，没有任何 Cookie，亚马逊不知道我们在哪，默认会给
        一个随机地区（实测出现过纽伦堡 90403）。同��商品在不同地区看到的
        库存和可售状态不同，不设配送地就等于用错视角判定。

        流程是亚马逊的两段式弹窗：
            点页头配送栏 → 填邮编 → 点 Bestätigen → 点 Fertig
        第二步完成后弹窗内容会变形（Bestätigen 消失，变成「Senden an 10115
        Ändern」），只点第一步不点 Fertig，配送地不会生效。

        关键约束：**必须从更新后的页面实际读回邮编**，读回值与目标一致才算
        成功。填了不等于生效 —— 亚马逊可能静默重置，也可能流程只走了一半。
        不回读就会拿着错误视角的截图去判定加购按钮，结论是错的且无从察觉。

        返回 None 表示成功；返回字符串表示失败原因（调用方据此终止扫描）。
        """
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
            #
            # 这里等的是「元素出现」而不是固定时长：弹窗是 JS 动态渲染的，死等
            # 1.5 秒在网络慢时会漏掉（曾因此报「找不到邮编框」，而真实原因
            # 是还没渲染完）。等具体元素没有猜测成分，元素一出现就立刻返回。
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
            # 截图放在等待成功之后拍，确保它反映的是弹窗的真实状态，
            # 而不是「可能还没打开」的中间态。
            await page.screenshot(path=str(diagnostic_dir / "delivery_dialog.png"), full_page=False)
            details["stage"] = "fill postal code"
            input_value = await field.input_value()
            if not postal_values_equal(input_value, postal_code):
                # 保留原有 5 秒清空和 8 秒输入上限，已有正确值时避开可能阻塞的输入校验。
                #
                # 用 type() 逐字输入而不是 fill() 一次性填充：亚马逊的邮编框对
                # fill() 的响应不稳定，会挂在输入校验上超时，而逐字输入模拟
                # 真人打字，校验能正常触发。
                try:
                    await field.click(timeout=5000)
                    await field.fill("", timeout=5000)
                except Exception:
                    pass
                await field.type(postal_code, delay=60, timeout=8000)
                input_value = await field.input_value()
            details["postal_input_value"] = input_value
            # 用规范化比较而非精确相等：亚马逊可能把 "SW1A 1AA" 显示成
            # "SW1A1AA"，规范化后两者才相等。
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
            # 无论成功失败都要把弹窗收干净，残留弹窗会遮挡加购按钮。
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
            # 最终校验：页头读回的文本必须包含目标邮编。失败信息区分两种情况 ——
            # 页头根本没显示（上面已返回）和页头显示了但邮编不符。
            if not postal_matches(details["delivery_text_after"], postal_code):
                return self._delivery_error(details, diagnostic_dir, f"页头仍显示：{details['delivery_text_after']}")
            return None
        except Exception as exc:
            return self._delivery_error(details, diagnostic_dir, f"delivery region setup failed: {type(exc).__name__}")

    @staticmethod
    def _delivery_error(details: dict, diagnostic_dir: Path, reason: str) -> str:
        """拼装配送失败信息。

        details 里记录了每一步的中间状态（stage、找到的邮编、点击是否成功等），
        一起写进错误信息，排查时不用再去翻截图猜卡在哪一步。
        """
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

        两级查找的顺序不能反：属性匹配更精确，结构兜底更宽泛。先精确后
        宽松，避免把「国家下拉」之类的控件当成邮编框。
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
        """定位「确认邮编」按钮。

        按可见文字匹配多语言说法（德语 Bestätigen、荷兰语 Toepassen、
        法语 Appliquer 等）。用「包含」匹配有风险：像「Abbrechen」（取消）
        这类词不含这些关键字，但「Bestätigen」也可能命中更长的父容器，
        所以拿到后还要靠 click 的可操作性检查兜底。
        """
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
