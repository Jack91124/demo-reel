# Changelog

## 0.1.0 — 2026-11-27

First public release.

### Added
- `demoreel render` — TOML script to MP4 or GIF, frames streamed straight into ffmpeg.
- `demoreel still` — single PNG frame at any timestamp.
- `demoreel inspect` — timeline and caption stats without rendering.
- `demoreel from-session` — convert a real **Claude Code** or **Codex** JSONL session log into a demo script, then optionally render it.
- Terminal mode (`cmd` / `out` / `clear` / `pause` / `banner`) and agent mode (`user` / `assistant` / `tool`) in one timeline.
- Six themes: github-dark, dracula, nord, light, midnight, solarized.
- Correct CJK double-width layout with per-script font fallback.
- Captions rendered as a bottom-of-frame pill.
- 39-test unittest suite (session fixtures are synthesised in temp dirs).

### Known limitations
- DSH `.jsonl.zstd` sessions are not decoded (no bundled zstd).
- Windows-terminal font auto-detection is a fixed path list; pass `font_path` to override.
