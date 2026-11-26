"""Cross-platform font discovery.

demo-reel draws text with real font files, so it needs a monospaced face and,
for CJK, a font that actually has the glyphs. Hard-coding a Windows path works
on exactly one machine; this module probes the usual install locations per
platform and degrades to Pillow's built-in bitmap font instead of crashing.

Every lookup is a plain file existence check - no font enumeration APIs, so it
behaves the same in a container as on a desktop.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, Optional

# (regular, bold) candidates per platform, most preferred first.
_MONO = {
    "win32": (
        ("C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/consolab.ttf"),
        ("C:/Windows/Fonts/CascadiaMono.ttf", "C:/Windows/Fonts/CascadiaMono.ttf"),
        ("C:/Windows/Fonts/lucon.ttf", "C:/Windows/Fonts/lucon.ttf"),
    ),
    "darwin": (
        ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Menlo.ttc"),
        ("/System/Library/Fonts/SFNSMono.ttf", "/System/Library/Fonts/SFNSMono.ttf"),
        ("/Library/Fonts/Courier New.ttf", "/Library/Fonts/Courier New Bold.ttf"),
    ),
    "linux": (
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"),
        ("/usr/share/fonts/TTF/DejaVuSansMono.ttf",
         "/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf"),
        ("/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
         "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf"),
    ),
}

# CJK faces. Only used for characters a Latin font cannot draw.
_CJK = {
    "win32": (
        ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"),
        ("C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simhei.ttf"),
        ("C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/YuGothM.ttc"),
    ),
    "darwin": (
        ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"),
        ("/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc"),
    ),
    "linux": (
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
         "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        ("/usr/share/fonts/truetype/arphic/uming.ttc",
         "/usr/share/fonts/truetype/arphic/uming.ttc"),
    ),
}

_WINDOWS_FONTS = "C:/Windows/Fonts"


def _first_pair(table, platform: str) -> Optional[tuple]:
    for regular, bold in table.get(platform, ()):
        if os.path.exists(regular):
            return (regular, bold if os.path.exists(bold) else regular)
    return None


def _glob_windows_mono() -> Optional[tuple]:
    """Last resort on Windows: any Consolas/Cascadia/Lucida file present."""
    if not os.path.isdir(_WINDOWS_FONTS):
        return None
    try:
        names = os.listdir(_WINDOWS_FONTS)
    except OSError:
        return None
    lowered = {n.lower(): n for n in names}
    for stem, bold_stem in (("consola.ttf", "consolab.ttf"),
                            ("cascadiamono.ttf", "cascadiamono.ttf"),
                            ("lucon.ttf", "lucon.ttf")):
        if stem in lowered:
            regular = os.path.join(_WINDOWS_FONTS, lowered[stem])
            bold_name = lowered.get(bold_stem, lowered[stem])
            return (regular, os.path.join(_WINDOWS_FONTS, bold_name))
    return None


def resolve(platform: Optional[str] = None, mono: Optional[str] = None,
            bold: Optional[str] = None, cjk: Optional[str] = None,
            cjk_bold: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Pick font paths for this machine.

    Explicit arguments always win, which is what `Renderer(font_path=...)` and the
    `--font` CLI flag pass through. Missing entries come back as None so the
    caller can fall back to Pillow's default font.
    """
    platform = platform or sys.platform

    if mono:
        mono_path, bold_path = mono, (bold or mono)
    else:
        pair = _first_pair(_MONO, platform) or (
            _glob_windows_mono() if platform == "win32" else None)
        mono_path, bold_path = pair if pair else (None, None)

    if cjk:
        cjk_path, cjk_bold_path = cjk, (cjk_bold or cjk)
    else:
        pair = _first_pair(_CJK, platform)
        cjk_path, cjk_bold_path = pair if pair else (None, None)

    return {
        "mono": mono_path,
        "bold": bold_path or mono_path,
        "cjk": cjk_path,
        "cjk_bold": cjk_bold_path or cjk_path,
    }
