import re
from urllib.parse import urlsplit

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.monitoring.config.markets import AMAZON_DOMAINS, ENTRY_COUNTRIES


class DemoResultRequest(BaseModel):
    result: Literal["healthy", "inventory_risk", "technical_failure"]


class ProductBatchDeleteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_ids: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        if len(set(self.product_ids)) != len(self.product_ids):
            raise ValueError("商品 ID 不能重复")
        return self


PLATFORM_DOMAINS = {
    "tiktok": ("tiktok.com",),
    "temu": ("temu.com",),
    "ebay": ("ebay.com", "ebay.de", "ebay.it", "ebay.fr", "ebay.es", "ebay.co.uk", "ebay.pl", "ebay.be"),
    "shein": ("shein.com",),
}


def amazon_asin(url: str) -> str:
    result = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)", urlsplit(url).path, re.I)
    return result[1].upper() if result else ""


class ProductEntryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    platform: Literal["amazon", "tiktok", "temu", "ebay", "shein"]
    store_code: Literal["H1-A1", "H2-A1", "H4-A1"]
    country: str = ""
    asin: str = Field(default="", max_length=10)
    sku: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=4096)
    added_by: Literal["Frank", "Lvy", "Nova", "Drake"]

    @model_validator(mode="after")
    def validate_market(self):
        if not self.country:
            raise ValueError("请选择站点信息，站点决定配送邮编")
        if self.country not in ENTRY_COUNTRIES:
            raise ValueError("请选择有效站点")
        url = urlsplit(self.url)
        host = url.hostname or ""
        if url.scheme != "https" or not host or url.username is not None or url.port is not None:
            raise ValueError("请填写有效的 HTTPS 商品链接")
        domains = (AMAZON_DOMAINS[self.country],) if self.platform == "amazon" else PLATFORM_DOMAINS[self.platform]
        if not any(host == domain or host.endswith("." + domain) for domain in domains):
            raise ValueError("链接域名与所选平台或站点不一致")
        if url.path in ("", "/"):
            raise ValueError("请填写商品详情页链接")
        if self.platform == "amazon":
            asin = amazon_asin(self.url)
            if not asin or (self.asin and self.asin.upper() != asin):
                raise ValueError("ASIN 与 Amazon 商品链接不一致")
            self.asin = asin
        return self
