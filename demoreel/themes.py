"""Color themes for demo-reel."""
from __future__ import annotations

GITHUB_DARK = {
    "desktop": "#05070c", "window": "#0d1117", "border": "#232a36",
    "titlebar": "#11161f", "titletext": "#7d8590",
    "fg": "#c9d1d9", "dim": "#6e7681", "green": "#3fb950", "blue": "#58a6ff",
    "yellow": "#d29922", "red": "#f85149", "purple": "#bc8cff", "cyan": "#39c5cf",
    "dot_red": "#ff5f57", "dot_yellow": "#febc2e", "dot_green": "#28c840",
    "caption_bg": "#161b22", "caption_fg": "#e6edf3", "caption_border": "#30363d",
}

DRACULA = {
    "desktop": "#191a21", "window": "#282a36", "border": "#44475a",
    "titlebar": "#21222c", "titletext": "#6272a4",
    "fg": "#f8f8f2", "dim": "#6272a4", "green": "#50fa7b", "blue": "#8be9fd",
    "yellow": "#f1fa8c", "red": "#ff5555", "purple": "#bd93f9", "cyan": "#8be9fd",
    "dot_red": "#ff5555", "dot_yellow": "#f1fa8c", "dot_green": "#50fa7b",
    "caption_bg": "#21222c", "caption_fg": "#f8f8f2", "caption_border": "#44475a",
}

NORD = {
    "desktop": "#1b2029", "window": "#2e3440", "border": "#4c566a",
    "titlebar": "#272c36", "titletext": "#7b88a1",
    "fg": "#d8dee9", "dim": "#616e88", "green": "#a3be8c", "blue": "#81a1c1",
    "yellow": "#ebcb8b", "red": "#bf616a", "purple": "#b48ead", "cyan": "#88c0d0",
    "dot_red": "#bf616a", "dot_yellow": "#ebcb8b", "dot_green": "#a3be8c",
    "caption_bg": "#272c36", "caption_fg": "#eceff4", "caption_border": "#4c566a",
}

LIGHT = {
    "desktop": "#eef1f5", "window": "#ffffff", "border": "#d7dee8",
    "titlebar": "#f6f8fa", "titletext": "#8b949e",
    "fg": "#1f2328", "dim": "#8b949e", "green": "#1a7f37", "blue": "#0969da",
    "yellow": "#9a6700", "red": "#cf222e", "purple": "#8250df", "cyan": "#1b7c83",
    "dot_red": "#ff5f57", "dot_yellow": "#febc2e", "dot_green": "#28c840",
    "caption_bg": "#f6f8fa", "caption_fg": "#1f2328", "caption_border": "#d7dee8",
}

MIDNIGHT = {
    "desktop": "#0a0b10", "window": "#12141d", "border": "#2a2f42",
    "titlebar": "#171a26", "titletext": "#6b7280",
    "fg": "#e5e7eb", "dim": "#6b7280", "green": "#34d399", "blue": "#60a5fa",
    "yellow": "#fbbf24", "red": "#f87171", "purple": "#a78bfa", "cyan": "#22d3ee",
    "dot_red": "#ff5f57", "dot_yellow": "#febc2e", "dot_green": "#28c840",
    "caption_bg": "#171a26", "caption_fg": "#f3f4f6", "caption_border": "#2a2f42",
}

SOLARIZED = {
    "desktop": "#001b26", "window": "#002b36", "border": "#0b4a5c",
    "titlebar": "#00212b", "titletext": "#586e75",
    "fg": "#eee8d5", "dim": "#657b83", "green": "#859900", "blue": "#268bd2",
    "yellow": "#b58900", "red": "#dc322f", "purple": "#6c71c4", "cyan": "#2aa198",
    "dot_red": "#dc322f", "dot_yellow": "#b58900", "dot_green": "#859900",
    "caption_bg": "#00212b", "caption_fg": "#eee8d5", "caption_border": "#0b4a5c",
}

THEMES = {
    "github-dark": GITHUB_DARK,
    "dracula": DRACULA,
    "nord": NORD,
    "light": LIGHT,
    "midnight": MIDNIGHT,
    "solarized": SOLARIZED,
}


def get(name: str) -> dict:
    if name in THEMES:
        return dict(THEMES[name])
    if name.startswith("#"):
        raise ValueError("a theme name is required, not a raw color")
    raise ValueError(f"unknown theme {name!r}; available: {', '.join(THEMES)}")
