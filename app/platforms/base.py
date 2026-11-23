from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlatformProfile:
    """
    Platform profile data model.
    描述平台的基本信息，包括名称、分类、浏览器配置、认证配置、选择器配置、提取配置、爬取配置。
    """
    name: str
    category: str
    browser: dict = field(default_factory=dict)
    auth: dict = field(default_factory=dict)
    selectors: dict = field(default_factory=dict)
    extraction: dict = field(default_factory=dict)
    crawl: dict = field(default_factory=dict)
    location: dict = field(default_factory=dict)
    delivery: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "PlatformProfile":
        return cls(
            name=data["name"],
            category=data.get("category", "generic"),
            browser=data.get("browser", {}),
            auth=data.get("auth", {}),
            selectors=data.get("selectors", {}),
            extraction=data.get("extraction", {}),
            crawl=data.get("crawl", {}),
            location=data.get("location", {}),
            delivery=data.get("delivery", {}),
            cookies=data.get("cookies", {}),
        )

    def get_selector(self, key: str) -> str | None:
        return self.selectors.get(key)

    def get_page_schema(self, page_type: str) -> dict:
        page_types = self.extraction.get("page_types", {})
        return page_types.get(page_type, {})

    def get_link_pattern(self, name: str) -> dict:
        return self.extraction.get("link_patterns", {}).get(name, {})

    @property
    def default_link_pattern(self) -> str | None:
        return self.extraction.get("default_link_pattern")

    @property
    def default_page_type(self) -> str | None:
        return self.extraction.get("default_page_type")

    @property
    def default_list_page_type(self) -> str | None:
        return self.extraction.get("default_list_page_type")

    @property
    def auth_required(self) -> bool:
        return self.auth.get("required", False)

    @property
    def home_url(self) -> str | None:
        return self.auth.get("home_url")

    @property
    def login_url(self) -> str | None:
        return self.auth.get("login_url")

    @property
    def logged_in_selectors(self) -> list[str]:
        return self.auth.get("logged_in_selectors", [])

    @property
    def login_form_selectors(self) -> list[str]:
        return self.auth.get("login_form_selectors", [])

    def selector_hints(self) -> str:
        if not self.selectors:
            return ""
        lines = [f"- {key}: {value}" for key, value in self.selectors.items()]
        return "\n".join(lines)

    def category_hints(self) -> str:
        hints: dict[str, str] = {
            "social": "社交媒体 SPA，class 通常不稳定，优先 aria-label / href。",
            "ecommerce": "电商页面，优先使用配置中的稳定 selector（id、data 属性）。",
            "saas": "SaaS 店铺页面，DOM 因主题而异，结合已知 selector 与 AI 定位。",
        }
        return hints.get(self.category, "通用网页，优先 id、aria-label、稳定结构。")

    def resolve_ready_selectors(self, url: str) -> list[str]:
        """根据 URL 找到页面主要内容已出现的 selector。"""
        schema = self._match_page_schema(url)
        if not schema:
            return []

        selectors = schema.get("ready_selectors") or []
        if isinstance(selectors, str):
            selectors = [selectors]
        if not selectors and schema.get("ready_selector"):
            selectors = [schema["ready_selector"]]
        if not selectors and schema.get("item_selector"):
            selectors = [schema["item_selector"]]
        return [selector for selector in selectors if selector]

    def resolve_optional_ready_selectors(self, url: str) -> list[str]:
        schema = self._match_page_schema(url)
        if not schema:
            return []
        selectors = schema.get("optional_ready_selectors") or []
        if isinstance(selectors, str):
            selectors = [selectors]
        return [selector for selector in selectors if selector]

    def _match_page_schema(self, url: str) -> dict | None:
        page_types = self.extraction.get("page_types", {})
        url_lower = url.lower()

        for schema in page_types.values():
            patterns = schema.get("url_patterns", [])
            if patterns and any(pattern.lower() in url_lower for pattern in patterns):
                return schema

        if self._looks_like_detail_page(url) and self.default_page_type:
            return page_types.get(self.default_page_type) or None

        return None

    def resolve_content_selector(self, url: str) -> str | None:
        """根据 URL 与 YAML page_types 配置，解析列表页内容就绪 selector。"""
        if self._looks_like_detail_page(url):
            return None

        page_types = self.extraction.get("page_types", {})
        url_lower = url.lower()

        for schema in page_types.values():
            patterns = schema.get("url_patterns", [])
            if not patterns:
                continue
            if any(p.lower() in url_lower for p in patterns):
                selector = schema.get("item_selector")
                if selector:
                    return selector

        default_list = self.default_list_page_type
        if default_list:
            selector = page_types.get(default_list, {}).get("item_selector")
            if selector:
                return selector

        return None

    def _looks_like_detail_page(self, url: str) -> bool:
        url_lower = url.lower()
        page_types = self.extraction.get("page_types", {})

        default_detail = self.default_page_type
        if default_detail:
            patterns = page_types.get(default_detail, {}).get("url_patterns", [])
            if patterns and any(p.lower() in url_lower for p in patterns):
                return True

        detail_hints = ("/p/", "/reel/", "/reels/", "/dp/", "/products/", "/video/")
        return any(h in url_lower for h in detail_hints)
