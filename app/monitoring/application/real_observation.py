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
    ) -> ScanObservation:
        started_at = datetime.now(timezone.utc)
        cookies = await _cookie_summary(page)
        dom_state = await _dom_add_to_cart_state(page)
        if dom_state is True:
            ocr_error_status = ProductScanStatus.HEALTHY
        elif dom_state is False:
            ocr_error_status = ProductScanStatus.INVENTORY_RISK
        else:
            ocr_error_status = ProductScanStatus.TECHNICAL_FAILURE
        try:
            result = await self.ocr.recognize(ImageRegion(roi_bytes))
        except Exception as exc:
            return _ocr_diagnostic(getattr(exc, "code", "OCR_FAILED"), str(exc), started_at, cookies, ocr_error_status)

        try:
            phrases = self.phrase_sets.load(product.country, product.platform, product.page_type)
            match = match_add_to_cart(result.text, phrases)
            if page is None:
                unavailable_phrases = self.phrase_sets.load(
                    product.country, product.platform, product.page_type, unavailable=True
                )
                unavailable = match_add_to_cart(result.text, unavailable_phrases).matched
        except Exception as exc:
            return _ocr_diagnostic("PHRASE_SET_LOAD_FAILED", str(exc), started_at, cookies, ocr_error_status)

        status = ocr_error_status
        error_code = None
        error_message = None
        if dom_state is True and not match.matched:
            error_code = "DOM_OCR_MISMATCH"
            error_message = "add-to-cart button is usable but OCR did not match configured phrases"
        elif dom_state is False and match.matched:
            error_code = "DOM_OCR_MISMATCH"
            error_message = "OCR matched add-to-cart text but the product has no usable add-to-cart button"
        elif page is None:
            if unavailable and not match.matched:
                status = ProductScanStatus.INVENTORY_RISK
            elif match.matched and not unavailable:
                status = ProductScanStatus.HEALTHY
            else:
                error_code = "OCR_AVAILABILITY_CONFLICT" if unavailable else "OCR_AVAILABILITY_UNVERIFIED"
                error_message = "OCR did not provide an unambiguous availability signal"
        elif dom_state is None:
            error_code = "DOM_BUTTON_UNVERIFIED"
            error_message = "could not confirm whether the add-to-cart button is usable"

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
                unverified = True
        return (None if unverified else False), None
    except Exception:
        return None, None


def _ocr_diagnostic(
    code: str,
    message: str,
    started_at: datetime,
    cookies: list[dict],
    status: ProductScanStatus,
) -> ScanObservation:
    return ScanObservation(
        status=status,
        error_code=code,
        error_message=message,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        cookie_summary=cookies,
    )
