from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from app.monitoring.config.catalog_schema import CatalogProductRecord
from app.monitoring.domain.models import Product


class CatalogValidationError(ValueError):
    """Raised when a product catalog cannot be used for scanning."""


class ProductCatalogLoader(Protocol):
    def load(self, path: str) -> list[Product]:
        ...


class JsonProductCatalogLoader:
    allowed_countries = frozenset({"DE", "IT", "FR"})

    def load(self, path: str) -> list[Product]:
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CatalogValidationError(f"invalid product catalog: {source}") from error

        records = self._records(payload)
        products: list[Product] = []
        seen_keys: set[tuple[str, str, str]] = set()
        for index, raw_record in enumerate(records):
            try:
                record = CatalogProductRecord.model_validate(raw_record)
            except ValidationError as error:
                raise CatalogValidationError(f"invalid product at index {index}: {error}") from error
            if record.country not in self.allowed_countries:
                raise CatalogValidationError(
                    f"unsupported country at index {index}: {record.country}"
                )

            identity = (record.country, record.platform, record.sku)
            if identity in seen_keys:
                raise CatalogValidationError(
                    "duplicate product market identity: "
                    f"{record.country}/{record.platform}/{record.sku}"
                )
            seen_keys.add(identity)

            if not record.enabled:
                continue
            products.append(
                Product(
                    id=record.id,
                    country=record.country,
                    platform=record.platform,
                    sku=record.sku,
                    name=record.name,
                    url=record.url,
                    page_type=record.page_type,
                    roi_profile_id=record.roi_profile,
                    enabled=True,
                    delivery_validation_required=record.delivery_validation_required,
                )
            )
        return products

    @staticmethod
    def _records(payload: object) -> list[object]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("products"), list):
            return payload["products"]
        raise CatalogValidationError("product catalog must be a JSON array or an object with products")
