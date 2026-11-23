from pathlib import Path

import yaml

from app.platforms.base import PlatformProfile

PLATFORMS_DIR = Path(__file__).parent
_cache: dict[str, PlatformProfile] = {}


def default_auth_path(platform_name: str, base_dir: Path | None = None) -> Path:
    root = base_dir or Path(__file__).resolve().parents[2]
    return root / "examples" / "auth" / f"{platform_name}.json"


class PlatformRegistry:
    """
    Platform registry class.
    平台注册类，用于加载平台配置文件，并缓存平台配置。
    """
    @classmethod
    def load(cls, name: str) -> PlatformProfile:
        if name in _cache:
            return _cache[name]

        for yaml_path in PLATFORMS_DIR.rglob("*.yaml"):
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if data.get("name") == name:
                profile = PlatformProfile.from_dict(data)
                _cache[name] = profile
                return profile

        available = ", ".join(cls.list_names()) or "(none)"
        raise KeyError(f"platform not found: {name}. available: {available}")

    @classmethod
    def list_names(cls) -> list[str]:
        names = []
        for yaml_path in PLATFORMS_DIR.rglob("*.yaml"):
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if data.get("name"):
                names.append(data["name"])
        return sorted(set(names))

    @classmethod
    def clear_cache(cls):
        _cache.clear()
