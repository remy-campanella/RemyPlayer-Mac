"""Load a named palette and a shared QSS file, ready for future theme choices."""
from dataclasses import dataclass
from collections.abc import Mapping
import json
from pathlib import Path
import re
from string import Template
from tempfile import TemporaryDirectory
from types import MappingProxyType

from PySide6.QtGui import QColor, QPalette

THEME_DIRECTORY = Path(__file__).resolve().parents[1] / "resources" / "themes"
DEFAULT_THEME = "black_gold"


@dataclass(frozen=True)
class Theme:
    """主题色、QSS 与临时着色图标的共同所有者；持有期间图标文件保持可用。"""
    id: str
    name: str
    dark: bool
    colors: Mapping[str, str]
    stylesheet: str
    assets: TemporaryDirectory

    def color(self, role):
        return QColor(self.colors[role])

    def palette(self):
        """由语义颜色构建 Qt 调色板，覆盖原生控件和禁用状态。"""
        palette = QPalette()
        roles = {
            "Window": "background", "WindowText": "text", "Base": "surface",
            "AlternateBase": "surface_alt", "ToolTipBase": "surface", "ToolTipText": "text",
            "Text": "text", "Button": "button", "ButtonText": "text", "BrightText": "accent_light",
            "Highlight": "selection", "HighlightedText": "accent_light", "Link": "accent",
            "LinkVisited": "accent_dark", "PlaceholderText": "text_muted", "Accent": "accent",
            "Light": "border", "Midlight": "border", "Dark": "background",
            "Mid": "border_subtle", "Shadow": "background",
        }
        for role, token in roles.items():
            palette.setColor(getattr(QPalette.ColorRole, role), self.color(token))
        for role in ("WindowText", "Text", "ButtonText", "PlaceholderText"):
            palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, role), self.color("text_disabled"))
        return palette


def load_theme(name=DEFAULT_THEME):
    """读取命名 JSON 和共用 QSS，校验后生成可应用的 Theme。

    名称只允许小写字母、数字和下划线；非法名称、颜色或 id 引发 ValueError。
    图标写入临时目录而非源码或签名应用包，调用方需持有返回对象。
    """
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError(f"Invalid theme name: {name}")
    data = json.loads((THEME_DIRECTORY / f"{name}.json").read_text(encoding="utf-8"))
    if data["id"] != name:
        raise ValueError("Theme id does not match its filename")
    colors = data["colors"]
    for token, value in colors.items():
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError(f"Invalid theme color {token}: {value}")
    source = Template((THEME_DIRECTORY / "base.qss").read_text(encoding="utf-8"))
    # Keep the generated, color-matched icons alive with this theme. No cache
    # is written into the source tree or the signed application bundle.
    assets = TemporaryDirectory(prefix="remyplayer-theme-")
    for icon in ("chevron.svg", "check.svg"):
        template = Template((THEME_DIRECTORY / icon).read_text(encoding="utf-8"))
        (Path(assets.name) / icon).write_text(template.substitute(colors), encoding="utf-8")
    stylesheet = source.substitute(colors, asset_dir=Path(assets.name).as_posix())
    theme = Theme(name, data["name"], data["dark"], MappingProxyType(colors), stylesheet, assets)
    theme.palette()  # Validate native palette roles as well as QSS variables.
    return theme
