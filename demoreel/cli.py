"""demo-reel CLI: scripted terminal demos -> MP4 / GIF, no screen recording."""
from __future__ import annotations

import argparse
import os
import sys
import time

from . import script as script_mod
from . import encode
from .term import (DEFAULT_FONT, DEFAULT_FONT_BOLD, DEFAULT_FONT_CJK,
                   DEFAULT_FONT_CJK_BOLD, Grid, Renderer, Style)


def _renderer_for(meta: dict) -> Renderer:
    """Build a renderer from a script's [meta] block, honouring font overrides."""
    return Renderer(
        width=int(meta.get("width", 1600)),
        height=int(meta.get("height", 900)),
        font_size=int(meta.get("font_size", 24)),
        title=meta.get("title", ""),
        theme=meta.get("theme"),
        font_path=meta.get("font") or DEFAULT_FONT,
        font_bold_path=meta.get("font_bold") or DEFAULT_FONT_BOLD,
        font_cjk=meta.get("font_cjk") or DEFAULT_FONT_CJK,
        font_cjk_bold=meta.get("font_cjk_bold") or DEFAULT_FONT_CJK_BOLD,
    )


def _apply(grid: Grid, ev, cur_style: dict) -> dict:
    if ev.kind == "clear":
        grid.reset()
    elif ev.kind == "char":
        if ev.payload == "\n":
            grid.newline()
        else:
            grid.put(ev.payload, Style(**ev.style))
    elif ev.kind == "banner":
        grid.banner(str(ev.payload), Style(**ev.style) if ev.style else Style())
    elif ev.kind == "line":
        st = Style(**ev.style) if ev.style else Style(fg=cur_style.get("fg", "fg"))
        grid.line(ev.payload, st)
    return cur_style


def render_script(spec_path: str, out: str, gif: bool = False, fps: int = None,
                  ffmpeg: str = None, crf: int = 18, on_progress=None) -> dict:
    demo = script_mod.parse(spec_path)
    meta = demo.meta
    r = _renderer_for(meta)
    fps = fps or int(meta.get("fps", 30))
    total = max(1, int(round(demo.duration * fps)))
    grid = Grid(r.cols, r.rows)
    idx = 0
    n_ev = len(demo.events)
    cur = {}

    def frames():
        nonlocal idx
        for f in range(total):
            t = f / fps
            while idx < n_ev and demo.events[idx].t <= t:
                ev = demo.events[idx]
                _apply(grid, ev, cur)
                idx += 1
            cap = script_mod.caption_at(demo, t)
            blink = (t % 1.0) < 0.55
            yield r.frame(grid, caption=cap, cursor_on=blink)
            if on_progress and f % max(1, total // 20) == 0:
                on_progress(f, total)

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    t0 = time.time()
    encode.stream(frames(), r.W, r.H, fps, out, ffmpeg=ffmpeg, crf=crf, gif=gif)
    return {"out": out, "frames": total, "fps": fps, "size": f"{r.W}x{r.H}",
            "duration": round(total / fps, 2), "cols": r.cols, "rows": r.rows,
            "seconds": round(time.time() - t0, 2)}


def still(spec_path: str, out_png: str, at: float = 1.0) -> str:
    demo = script_mod.parse(spec_path)
    meta = demo.meta
    r = _renderer_for(meta)
    grid = Grid(r.cols, r.rows)
    for ev in demo.events:
        if ev.t > at:
            break
        _apply(grid, ev, {})
    img = r.frame(grid, caption=script_mod.caption_at(demo, at), cursor_on=True)
    img.save(out_png)
    return out_png


def _trim_steps(msgs, limit: int):
    """Keep whole turns: never cut a tool call away from its own output."""
    out = []
    for m in msgs:
        out.append(m)
        if len(out) >= limit:
            break
    return out


def _default_title(session: str) -> str:
    stem = os.path.splitext(os.path.basename(session))[0]
    return stem[:1].upper() + stem[1:] if stem else "session"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="demoreel",
                                 description="Scripted, pixel-perfect terminal demos as MP4/GIF.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("render", help="render a TOML demo script to MP4/GIF")
    p.add_argument("spec")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--gif", action="store_true")
    p.add_argument("--fps", type=int)
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--ffmpeg")
    p.add_argument("--quiet", action="store_true")

    s = sub.add_parser("still", help="render a single PNG frame")
    s.add_argument("spec")
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--at", type=float, default=1.0)

    v = sub.add_parser("inspect", help="print timeline stats without rendering")
    v.add_argument("spec")

    c = sub.add_parser("from-session", help="convert a real agent session log into a TOML demo script")
    c.add_argument("session", help="Claude Code or Codex JSONL session file")
    c.add_argument("-o", "--out", required=True)
    c.add_argument("--title")
    c.add_argument("--theme", default="dracula")
    c.add_argument("--no-tools", action="store_true", help="only user/assistant turns")
    c.add_argument("--max-tool-lines", type=int, default=4)
    c.add_argument("--line-width", type=int, default=96)
    c.add_argument("--banner")
    c.add_argument("--max-steps", type=int, default=0,
                   help="keep only the first N steps (0 = all)")
    c.add_argument("--render", metavar="MP4", help="also render the converted script")
    c.add_argument("--gif", action="store_true")

    a = ap.parse_args(argv)
    if a.cmd == "render":
        prog = None
        if not a.quiet:
            prog = lambda f, t: print(f"\r  frame {f}/{t}", end="", file=sys.stderr)
        info = render_script(a.spec, a.out, gif=a.gif, fps=a.fps, ffmpeg=a.ffmpeg,
                             crf=a.crf, on_progress=prog)
        if prog:
            print(file=sys.stderr)
        print(f"{info['out']}  {info['size']}  {info['duration']}s  {info['frames']} frames "
              f"({info['seconds']}s to render)")
        return 0
    if a.cmd == "still":
        print(still(a.spec, a.out, a.at))
        return 0
    if a.cmd == "from-session":
        from . import fromsession
        try:
            msgs = fromsession.load_session(a.session)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not msgs:
            print("error: no renderable messages found", file=sys.stderr)
            return 2
        if a.max_steps and a.max_steps > 0:
            msgs = _trim_steps(msgs, a.max_steps)
        if a.title is None:
            a.title = _default_title(a.session)
        banner = a.banner
        if banner is None:
            fmt = fromsession.detect_format(a.session)
            agent = "claude-code" if fmt == "claude" else "codex"
            banner = f"session  {fromsession._session_stamp(a.session)}  {agent}  " \
                     f"{os.path.basename(os.path.dirname(a.session))[:40]}"
        doc = fromsession.to_toml(msgs, title=a.title, theme=a.theme,
                                  include_tools=not a.no_tools, banner=banner,
                                  max_tool_lines=a.max_tool_lines,
                                  line_width=a.line_width)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(doc)
        print(f"{a.out}  {len(msgs)} steps")
        if a.render:
            info = render_script(a.out, a.render, gif=a.gif)
            print(f"{info['out']}  {info['size']}  {info['duration']}s  {info['frames']} frames")
        return 0
    if a.cmd == "inspect":
        d = script_mod.parse(a.spec)
        print(f"duration={d.duration:.2f}s events={len(d.events)} captions={len(d.captions)}")
        for c in d.captions:
            print(f"  {c.t0:6.2f}-{c.t1:6.2f}  {c.text}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
