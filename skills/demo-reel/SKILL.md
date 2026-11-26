---
name: demo-reel
description: Render a terminal demo, CLI walkthrough, or AI agent session into an MP4/GIF video from a text file, with no screen recording and no browser. Use when the user wants a demo GIF for a README, a reproducible terminal screencast, a video of a Claude Code / Codex session, or needs to re-render an existing demo after a copy change.
license: MIT
metadata:
  version: "0.1.0"
  homepage: "https://github.com/Jack91124/demo-reel"
  source: "https://github.com/Jack91124/demo-reel"
---

# demo-reel

Turn a text file into a pixel-perfect terminal demo video. Frames are drawn character by
character with Pillow and piped into ffmpeg — nothing is captured from a screen, so the same
input always produces the same output.

## When to use

- The user needs a demo GIF/MP4 for a README, docs site, or release announcement.
- The user wants a terminal screencast they can re-render after changing the copy.
- The user wants to show an AI agent session (Claude Code, Codex) but has only the JSONL log.
- The user is about to record their desktop and the result would contain their wallpaper,
  notifications, or a stale version of the tool.

Do **not** use this for a live TUI that redraws itself, real ANSI art, or cursor addressing —
demo-reel is a renderer, not a terminal emulator. Use VHS in that case.

## Prerequisites

- Python 3.11+ and `ffmpeg` on `PATH` (`--ffmpeg` overrides the lookup).
- Install: `pip install "git+https://github.com/Jack91124/demo-reel"` (PyPI release pending).

Verify with `demoreel --help`. If it fails with "ffmpeg not found", install ffmpeg
(`winget install Gyan.FFmpeg` / `brew install ffmpeg` / `apt install ffmpeg`).

## Core workflow

1. **Inspect before rendering.** `demoreel inspect <script.toml>` prints duration, event count,
   and the caption timeline. It costs nothing and catches a 90-second demo before you render it.
2. **Write the script.** A TOML file with a `[meta]` table and a list of `[[steps]]`.
   Terminal steps: `cmd` (types character by character), `out` (prints lines at once),
   `clear`, `pause`, `banner`. Agent steps: `user`, `assistant`, `tool`.
3. **Render a still first.** `demoreel still <script.toml> -o poster.png --at 6.5` gives you a
   PNG in a second — check fonts, theme, and line wrapping before spending time on the full video.
4. **Render.** `demoreel render <script.toml> -o demo.mp4` (or `--gif` for a palette-optimised,
   1200px-wide GIF suitable for a README). Rendering runs roughly at real time.
5. **Commit the TOML, not just the video.** That is the point: the demo becomes reviewable in a
   pull request and re-renderable later.

## Converting a real agent session

```bash
demoreel from-session ~/.claude/projects/<munged-cwd>/<uuid>.jsonl \
  -o demos/that-bugfix.toml --max-steps 16 --render demo.mp4
```

Auto-detects Claude Code (`~/.claude/projects/**/*.jsonl`) and Codex
(`~/.codex/archived_sessions/rollout-*.jsonl`). It strips ANSI, drops `<system-reminder>` blocks,
flattens prose to one line, removes markdown, discards mojibake, clips long tool output, pairs
tool calls with their results, and paints failures red. Use `--max-steps` to keep a demo short.

Ask before you convert: session logs can contain client names, file paths, and prompts the user
did not expect to publish. Read the generated TOML and offer to trim it.

## Themes and layout

`github-dark`, `dracula`, `nord`, `light`, `midnight`, `solarized`. Set `theme` in `[meta]`,
plus `width`/`height`/`font_size`/`fps`. CJK glyphs get double-width cells and a fallback font,
so Chinese and Japanese captions do not overlap.

## Rules

- Never claim a demo exists until `demoreel render` exited 0 and the output file is non-empty.
  Report the real numbers: duration, frame count, file size.
- Prefer `--gif` for README embeds (hundreds of KB) and MP4 for release pages and social posts.
- If a font is missing the renderer falls back to Pillow's bitmap face rather than crashing —
  say so instead of shipping a demo that looks broken.
- Keep secrets out of scripts: `cmd` steps and session transcripts are committed to the repo.
