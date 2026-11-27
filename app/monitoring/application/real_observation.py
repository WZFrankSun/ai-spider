from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

from app.monitoring.application.cookie_summary import summarize_cookies
from app.monitoring.application.phrase_matching import JsonPhraseSetLoader, match_add_to_cart
from app.monitoring.application.ports import ImageRegion, OcrEngine
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


ADD_TO_CART_SELECTOR = (
    'button#add-to-cart-button, input#add-to-cart-button[type="submit"], '
    'input#add-to-cart-button[type="button"], #add-to-cart-button[role="button"]'
)


class RealObservationFactory:
    def __init__(self, ocr: OcrEngine, phrase_sets: JsonPhraseSetLoader | str | Path):
        self.ocr = ocr
        self.phrase_sets = (
            phrase_sets
            if hasattr(phrase_sets, "load")
            else JsonPhraseSetLoader(phrase_sets)
        )

    async def __call__(
        self,
        product: Product,
        page: object | None,
        roi_bytes: bytes,
        *,
        dom_evidence: tuple[bool | None, object | None] | None = None,
    ) -> ScanObservation:
        started_at = datetime.now(timezone.utc)
        cookies = await _cookie_summary(page)
        # dom_state 是三态，不是布尔：
        #   True  = DOM 里确认有可用按钮
        #   False = DOM 里确认没有可用按钮
        #   None  = 无法确认（按钮存在但点不动、被遮挡、探测超时）
        # False 和 None 的区分是判定安全性的关键：只有 False 才允许判库存风险。
        dom_state = dom_evidence[0] if dom_evidence is not None else await _dom_add_to_cart_state(page)
        try:
            result = await self.ocr.recognize(ImageRegion(roi_bytes))
        except Exception as exc:
            # OCR 本身失败属于「识别环节失败」，结果不可判定，一律技术故障。
            return _ocr_diagnostic(getattr(exc, "code", "OCR_FAILED"), str(exc), started_at, cookies)

        try:
            # 两套词库：加购词用于确认「能买」，不可购词用于佐证「买不了」。
            phrases = self.phrase_sets.load(product.country, product.platform, product.page_type)
            match = match_add_to_cart(result.text, phrases)
            unavailable_phrases = self.phrase_sets.load(
                product.country, product.platform, product.page_type, unavailable=True
            )
            unavailable = match_add_to_cart(result.text, unavailable_phrases).matched
        except Exception as exc:
            return _ocr_diagnostic("PHRASE_SET_LOAD_FAILED", str(exc), started_at, cookies)

        status = ProductScanStatus.TECHNICAL_FAILURE
        error_code = None
        error_message = None
        # 判定采用「DOM + OCR 双证据」，两者一致才下结论，矛盾时宁可报技术故障
        # 也不猜 —— 猜错会生成错误的库存告警，误报比漏报代价更高。
        if dom_state is True and match.matched:
            # DOM 有可用按钮，且 OCR 读到加购文案 —— 两者互证。
            status = ProductScanStatus.HEALTHY
        elif dom_state is True or (dom_state is False and match.matched):
            # 一个说有按钮另一个说没有（或反之），证据冲突，无法判定。
            error_code = "DOM_OCR_MISMATCH"
            error_message = "DOM button availability and OCR add-to-cart evidence disagree"
        elif page is not None and dom_state is None:
            # DOM 探测无法确认（按钮存在但点不动），且 OCR 也没读到加购文案。
            error_code = "DOM_BUTTON_UNVERIFIED"
            error_message = "could not confirm whether the add-to-cart button is usable"
        elif dom_state is False and not match.matched:
            # DOM 已确认页面里没有可用的加购按钮，且 OCR 也没读到加购文案，
            # 可以判定为库存风险。部分站点（如西班牙站）在无货时只显示愿望单
            # 按钮而不写任何不可购买文案，此时是否判风险由 DOM 结论决定。
            status = ProductScanStatus.INVENTORY_RISK
        elif unavailable and not match.matched:
            # DOM 无法确认，但 OCR 明确读到了「暂时无货」这类文案 —— 也判库存风险。
            status = ProductScanStatus.INVENTORY_RISK
        else:
            # 两个证据都不足以支撑任何结论，只能报技术故障，不生成库存告警。
            error_code = "OCR_AVAILABILITY_CONFLICT" if unavailable else "OCR_AVAILABILITY_UNVERIFIED"
            error_message = "OCR did not provide unambiguous unavailability evidence"

        finished_at = datetime.now(timezone.utc)
        return ScanObservation(
            status=status,
            ocr_text=result.text,
            matched_phrase=match.matched_phrase,
            confidence=result.confidence,
            started_at=started_at,
            finished_at=finished_at,
            error_code=error_code,
            error_message=error_message,
            cookie_summary=cookies,
        )


async def _cookie_summary(page: object | None) -> list[dict]:
    context = getattr(page, "context", None)
    cookies_method = getattr(context, "cookies", None)
    if cookies_method is None:
        return []
    try:
        cookies = cookies_method()
        if inspect.isawaitable(cookies):
            cookies = await cookies
        return summarize_cookies(cookies or [])
    except Exception:
        return []


async def _dom_add_to_cart_state(page: object | None) -> bool | None:
    state, _ = await find_usable_add_to_cart_button(page)
    return state


async def find_usable_add_to_cart_button(page):
    """探测页面上是否存在可用的加购按钮。

    返回 (dom_state, 按钮元素)：
      (True,  按钮)  确认有可用按钮
      (False, None)  确认没有可用按钮
      (None,  None)  无法确认

    「可用」比「存在」严格，三个条件缺一不可：
      1. is_visible()   —— 有尺寸且没被遮挡。Cookie 弹窗或配送弹窗残留时，
                         加购按钮虽然存在于 DOM 中，但被遮住会被判为不可见；
      2. is_enabled()   —— 没有 disabled 属性；
      3. click(trial=True) —— Playwright 的可操作性检查（能滚动到、能接收
                         事件、不被别的元素挡住），**不会真的点击**。这一步
                         超时 2 秒，是本函数的主要耗时来源。

    多报价商品会有多个同 id 的按钮，需要逐个检查，遇到第一个可用的就返回。
    注意区分 False 和 None：全部候选都「不可见/禁用」说明确实没有按钮
    （False）；有候选可见但试点击失败说明存在却不可用（None），后者不能
    用来判库存风险。

    ADD_TO_CART_SELECTOR 列了同一 id 的四种标签形态，因为不同站点的加购
    按钮有时是 <button>，有时是 <input type="submit">。
    """
    locator_factory = getattr(page, "locator", None)
    if locator_factory is None:
        return None, None
    try:
        locator = locator_factory(ADD_TO_CART_SELECTOR)
        count = await locator.count()
        unverified = False
        for index in range(count):
            candidate = locator if count == 1 else locator.nth(index)
            try:
                if not await candidate.is_visible() or not await candidate.is_enabled():
                    continue
                # Run Playwright actionability checks without sending a click.
                await candidate.click(trial=True, timeout=2_000)
                return True, candidate
            except Exception:
                # 有候选但通不过可操作性检查，记为「无法确认」而非「没有」。
                unverified = True
        return (None if unverified else False), None
    except Exception:
        return None, None


def _ocr_diagnostic(
    code: str,
    message: str,
    started_at: datetime,
    cookies: list[dict],
) -> ScanObservation:
    return ScanObservation(
        status=ProductScanStatus.TECHNICAL_FAILURE,
        error_code=code,
        error_message=message,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        cookie_summary=cookies,
    )
