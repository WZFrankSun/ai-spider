from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class CatalogProductRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    country: str
    platform: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    url: str = Field(min_length=1)
    page_type: str = Field(default="product_detail", min_length=1)
    roi_profile: str = Field(min_length=1)
    name: str = ""
    enabled: StrictBool = True
    delivery_validation_required: StrictBool = True
    postal_code: str = ""

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("postal_code")
    @classmethod
    def normalize_postal_code(cls, value: str) -> str:
        return value.strip()

