"""Terminal grid + frame renderer (PIL only).

Layout rules
------------
The grid is monospaced, but CJK is double width. A wide glyph therefore owns
two cells: the character plus a None placeholder that the renderer skips.
Without this a Chinese line would overlap itself, which is the single most
visible defect in a demo of a Chinese session.

ASCII is drawn with a monospaced font, CJK with a matching CJK font, both on a
shared baseline so mixed runs stay level.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import fonts as fontlib
from .themes import THEMES, get as get_theme

# Resolved once at import: explicit paths, then PATH-adjacent platform defaults,
# then None (meaning "use Pillow's built-in face").
_FONTS = fontlib.resolve()
DEFAULT_FONT = _FONTS["mono"]
DEFAULT_FONT_BOLD = _FONTS["bold"]
DEFAULT_FONT_CJK = _FONTS["cjk"]
DEFAULT_FONT_CJK_BOLD = _FONTS["cjk_bold"]


def _load_font(path, size):
    """Load a TrueType face, or fall back to Pillow's default face."""
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)      # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()

DEFAULT_THEME = {
    "desktop": "#05070c",
    "window": "#0d1117",
    "border": "#232a36",
    "titlebar": "#11161f",
    "titletext": "#7d8590",
    "fg": "#c9d1d9",
    "dim": "#6e7681",
    "green": "#3fb950",
    "blue": "#58a6ff",
    "yellow": "#d29922",
    "red": "#f85149",
    "purple": "#bc8cff",
    "cyan": "#39c5cf",
    "dot_red": "#ff5f57",
    "dot_yellow": "#febc2e",
    "dot_green": "#28c840",
    "caption_bg": "#161b22",
    "caption_fg": "#e6edf3",
    "caption_border": "#30363d",
}

NAMED = {
    "fg": "fg", "dim": "dim", "green": "green", "blue": "blue", "yellow": "yellow",
    "red": "red", "purple": "purple", "cyan": "cyan",
}


def hexrgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def is_wide(ch: str) -> bool:
    """True for characters that occupy two terminal cells."""
    if not ch:
        return False
    return unicodedata.east_asian_width(ch) in ("W", "F")


def display_width(text: str) -> int:
    """Visible cell count of a string."""
    return sum(2 if is_wide(c) else 1 for c in text)


@dataclass
class Style:
    fg: str = "fg"
    bg: Optional[str] = None
    bold: bool = False


class Grid:
    """A cols x rows character grid with per-cell style."""

    def __init__(self, cols: int, rows: int):
        self.cols = cols
        self.rows = rows
        self.cells = [[(" ", Style()) for _ in range(cols)] for _ in range(rows)]
        self.row = 0
        self.col = 0

    def reset(self):
        self.cells = [[(" ", Style()) for _ in range(self.cols)] for _ in range(self.rows)]
        self.row = 0
        self.col = 0

    def _scroll(self):
        self.cells.pop(0)
        self.cells.append([(" ", Style()) for _ in range(self.cols)])

    def newline(self):
        self.col = 0
        self.row += 1
        if self.row >= self.rows:
            self._scroll()
            self.row = self.rows - 1

    def put(self, ch: str, style: Style):
        w = 2 if is_wide(ch) else 1
        if self.col + w > self.cols:
            self.newline()
        self.cells[self.row][self.col] = (ch, style)
        if w == 2:
            self.cells[self.row][self.col + 1] = (None, style)
        self.col += w

    def write(self, text: str, style: Style):
        for ch in text:
            self.put(ch, style)

    def line(self, text: str, style: Style):
        self.write(text, style)
        self.newline()

    def banner(self, text: str, style: Style):
        st = Style(fg=style.fg or "fg", bg=style.bg or "caption_bg", bold=True)
        room = self.cols - 3
        out = []
        used = 0
        for ch in text:
            w = 2 if is_wide(ch) else 1
            if used + w > room:
                out.append("…")
                used += 1
                break
            out.append(ch)
            used += w
        pad = self.cols - used - 2
        self.line(" " + "".join(out) + " " * max(0, pad), st)


class Renderer:
    def __init__(self, width=1600, height=900, font_size=24, title="", theme=None,
                 cols=None, rows=None, font_path=DEFAULT_FONT,
                 font_bold_path=DEFAULT_FONT_BOLD,
                 font_cjk=DEFAULT_FONT_CJK, font_cjk_bold=DEFAULT_FONT_CJK_BOLD):
        self.W, self.H = width, height
        self.theme = get_theme(theme) if isinstance(theme, str) else dict(DEFAULT_THEME)
        if isinstance(theme, dict):
            self.theme.update(theme)
        self.title = title
        self.font_size = font_size
        self.font = _load_font(font_path, font_size)
        self.font_bold = _load_font(font_bold_path or font_path, font_size)
        self.title_font = _load_font(font_bold_path or font_path, max(11, int(font_size * 0.72)))
        self.caption_font = _load_font(font_bold_path or font_path, max(13, int(font_size * 0.86)))
        self.font_cjk = _load_font(font_cjk, font_size) if font_cjk else self.font
        self.font_cjk_bold = (_load_font(font_cjk_bold, font_size)
                              if font_cjk_bold else self.font_cjk)

        self.title_h = max(38, int(font_size * 1.9))
        self.pad_x = int(font_size * 0.9)
        self.pad_y = int(font_size * 0.75)
        self.win_margin = max(24, int(font_size * 1.6))

        self.win_box = (
            self.win_margin,
            self.win_margin,
            self.W - self.win_margin,
            self.H - self.win_margin - int(font_size * 1.4),
        )
        self.radius = max(10, int(font_size * 0.8))

        self.term_x = self.win_box[0] + self.pad_x
        self.term_y = self.win_box[1] + self.title_h + self.pad_y

        adv = self.font.getlength("M")
        cjk_adv = self.font_cjk.getlength("中")
        self.cell_w = max(6, int(round(max(adv, cjk_adv / 2.0))))

        bb = self.font.getbbox("Mg")
        h_ascii = bb[3] - bb[1]
        try:
            bc = self.font_cjk.getbbox("中")
            h_cjk = bc[3] - bc[1]
        except Exception:
            h_cjk = h_ascii
        self.cell_h = max(10, int(round(h_ascii * 1.52)), int(round(h_cjk * 1.30)))

        inner_w = self.win_box[2] - self.term_x - self.pad_x
        inner_h = self.win_box[3] - self.term_y - self.pad_y
        self.cols = cols or max(20, inner_w // self.cell_w)
        self.rows = rows or max(6, inner_h // self.cell_h)

        self.baseline = int(round(self.cell_h * 0.78))

        self.base = self._build_base()

    def _build_base(self) -> Image.Image:
        W, H = self.W, self.H
        base = Image.new("RGB", (W, H), hexrgb(self.theme["desktop"]))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(sh)
        x0, y0, x1, y1 = self.win_box
        d.rounded_rectangle((x0 + 6, y0 + 14, x1 + 6, y1 + 16), radius=self.radius,
                            fill=(0, 0, 0, 190))
        sh = sh.filter(ImageFilter.GaussianBlur(26))
        base = Image.alpha_composite(base.convert("RGBA"), sh).convert("RGB")

        d = ImageDraw.Draw(base)
        d.rounded_rectangle(self.win_box, radius=self.radius, fill=hexrgb(self.theme["window"]),
                            outline=hexrgb(self.theme["border"]), width=2)
        d.rounded_rectangle((x0, y0, x1, y0 + self.title_h + self.radius),
                            radius=self.radius, fill=hexrgb(self.theme["titlebar"]))
        d.rounded_rectangle((x0, y0 + self.title_h, x1, y0 + self.title_h + self.radius),
                            radius=0, fill=hexrgb(self.theme["window"]))
        d.line((x0, y0 + self.title_h, x1, y0 + self.title_h), fill=hexrgb(self.theme["border"]), width=1)
        cy = y0 + self.title_h // 2
        r = max(5, int(self.font_size * 0.28))
        for i, key in enumerate(("dot_red", "dot_yellow", "dot_green")):
            cx = x0 + int(self.font_size * 1.15) + i * int(r * 2.9)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=hexrgb(self.theme[key]))
        if self.title:
            tw = self.title_font.getlength(self.title)
            d.text(((W - tw) / 2, cy - self.title_font.size * 0.62), self.title,
                   font=self.title_font, fill=hexrgb(self.theme["titletext"]))
        return base

    def _color(self, name: str):
        return hexrgb(self.theme.get(name, name if name.startswith("#") else self.theme["fg"]))

    def frame(self, grid: Grid, caption: Optional[str] = None, cursor_on: bool = True) -> Image.Image:
        img = self.base.copy()
        d = ImageDraw.Draw(img)

        for r in range(self.rows):
            y = self.term_y + r * self.cell_h
            row = grid.cells[r]

            # background runs: merge equal bg colours into one rectangle
            c = 0
            while c < self.cols:
                st = row[c][1]
                if st.bg:
                    j = c
                    while j < self.cols and row[j][1].bg == st.bg:
                        j += 1
                    d.rectangle((self.term_x + c * self.cell_w, y,
                                 self.term_x + j * self.cell_w, y + self.cell_h),
                                fill=self._color(st.bg))
                    c = j
                else:
                    c += 1

            # text runs: merge cells sharing a style, then split by script
            c = 0
            while c < self.cols:
                st = row[c][1]
                ch = row[c][0]
                if ch is None or (ch == " " and not st.bg):
                    c += 1
                    continue
                j = c + 1
                while j < self.cols and row[j][1].fg == st.fg and row[j][1].bold == st.bold:
                    j += 1
                k = c
                while k < j:
                    if row[k][0] is None:
                        k += 1
                        continue
                    wide = is_wide(row[k][0])
                    m = k + 1
                    while m < j and (row[m][0] is None or is_wide(row[m][0]) == wide):
                        m += 1
                    text = "".join(row[q][0] for q in range(k, m) if row[q][0])
                    if text.strip():
                        if st.bold:
                            font = self.font_cjk_bold if wide else self.font_bold
                        else:
                            font = self.font_cjk if wide else self.font
                        d.text((self.term_x + k * self.cell_w, y + self.baseline), text,
                               font=font, fill=self._color(st.fg), anchor="ls")
                    k = m
                c = j

        if cursor_on and grid.row < self.rows:
            cx = self.term_x + grid.col * self.cell_w
            cy = self.term_y + grid.row * self.cell_h
            d.rectangle((cx, cy + 2, cx + self.cell_w - 2, cy + self.cell_h - 3),
                        fill=self._color("fg"))

        if caption:
            self._draw_caption(d, caption)
        return img

    def _draw_caption(self, d: ImageDraw.ImageDraw, text: str):
        pad_x, pad_y = int(self.font_size * 0.85), int(self.font_size * 0.42)
        tw = self.caption_font.getlength(text)
        th = self.caption_font.size
        bw, bh = tw + pad_x * 2, th + pad_y * 2
        bx = (self.W - bw) / 2
        by = self.H - bh - int(self.font_size * 0.55)
        d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=int(bh / 2),
                            fill=hexrgb(self.theme["caption_bg"]),
                            outline=hexrgb(self.theme["caption_border"]), width=1)
        d.text((bx + pad_x, by + bh / 2), text, font=self.caption_font,
               fill=hexrgb(self.theme["caption_fg"]), anchor="ls")
