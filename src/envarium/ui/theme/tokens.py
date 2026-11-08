"""设计令牌：颜色与排版的唯一来源，Light / Dark 各一套。"""

from __future__ import annotations

from dataclasses import dataclass

from envarium.infrastructure.config_store import Theme


@dataclass(frozen=True, slots=True)
class Palette:
    window: str
    surface: str
    surface_alt: str
    hover: str
    border: str
    text: str
    text_secondary: str
    accent: str
    accent_hover: str
    accent_soft: str
    success: str
    warning: str
    danger: str


LIGHT = Palette(
    window="#f3f3f3",
    surface="#ffffff",
    surface_alt="#fafafa",
    hover="#ededed",
    border="#e0e0e0",
    text="#1b1b1b",
    text_secondary="#6b6b6b",
    accent="#0a7cf6",
    accent_hover="#0868cf",
    accent_soft="#e7f1fd",
    success="#0f7b0f",
    warning="#9d5d00",
    danger="#c42b1c",
)

DARK = Palette(
    window="#1f1f1f",
    surface="#272727",
    surface_alt="#2b2b2b",
    hover="#333333",
    border="#3a3a3a",
    text="#f5f5f5",
    text_secondary="#a6a6a6",
    accent="#4cc2ff",
    accent_hover="#7ad1ff",
    accent_soft="#1d3b4d",
    success="#6ccb5f",
    warning="#fce100",
    danger="#ff99a4",
)


def palette_for(theme: Theme) -> Palette:
    return DARK if theme is Theme.DARK else LIGHT
