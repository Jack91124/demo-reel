"""Turn a real agent session log into a demo-reel TOML script.

Supported inputs
----------------
* Claude Code   ~/.claude/projects/<project>/<session>.jsonl
* Codex CLI     ~/.codex/archived_sessions/rollout-*.jsonl

Both are append-only JSONL. They are normalised into a small list of Msg
records (user text, assistant text, tool call + its output) and then emitted as
a TOML script that renders exactly like a hand-written demo.

Design notes
------------
* Everything is flattened to one screen line per message, because the grid has
  no word wrapping. Truncation is explicit and marked with an ellipsis.
* Tool output is the noisiest part of a real session, so it is capped hard
  (default 4 lines, 96 columns) and control characters are stripped: raw
  terminal logs contain CR, ANSI escapes and box drawing that would shred the
  layout.
* Nothing is invented. If the session has no assistant text after a tool call
  the demo simply has no such step.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from .term import display_width
from typing import Iterable, List, Optional, Sequence

__all__ = [
    "Msg", "load_session", "load_claude", "load_codex", "detect_format",
    "to_toml", "convert", "clean", "flatten", "clip_lines",
]

_ANSI = re.compile(
    chr(27) + r"\[[0-9;?]*[ -/]*[@-~]"        # CSI sequences
    + "|" + chr(27) + r"\][^\x07\x1b]*(?:\x07|\x1b\\)"   # OSC sequences
    + "|" + chr(27) + r"[@-Z\\-_]"              # two-byte escapes
)
_CTRL = re.compile("[\x00-\x08\x0b-\x1f\x7f]")


@dataclass
class Msg:
    """One normalised event from a session log."""

    role: str                      # user | assistant | tool
    text: str = ""
    tool: str = ""                 # tool name, role == "tool"
    call: str = ""                 # one-line argument summary
    lines: List[str] = field(default_factory=list)   # tool output lines
    error: bool = False


# --------------------------------------------------------------------------- #
# cleaning helpers
# --------------------------------------------------------------------------- #

def clean(text: str) -> str:
    """Strip ANSI escapes, CR and other control characters from log text."""
    if not text:
        return ""
    text = _ANSI.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CTRL.sub("", text)
    return text


_MD_EMPH = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_MD_CODE = re.compile(r"`([^`]+)`")


def _is_cjk(ch: str) -> bool:
    """True when joining this character needs no space (CJK text has none)."""
    return bool(ch) and display_width(ch) == 2


def strip_markdown(text: str) -> str:
    """Drop emphasis / inline-code markers that read as noise on screen."""
    text = _MD_EMPH.sub(lambda m: m.group(1) or m.group(2), text)
    text = _MD_CODE.sub(lambda m: m.group(1), text)
    return text.replace("**", "")


def _clip(text: str, width: int) -> str:
    """Truncate to a terminal-cell budget (CJK occupies two cells)."""
    if display_width(text) <= width:
        return text
    out = []
    used = 0
    for ch in text:
        w = 2 if display_width(ch) == 2 else 1
        if used + w > width - 1:
            break
        out.append(ch)
        used += w
    return "".join(out).rstrip() + "\u2026"


def flatten(text: str, width: int = 100) -> str:
    """Collapse a multi-line blob into one truncated screen line."""
    text = clean(text)
    parts = [p.strip() for p in text.split("\n")]
    joined = ""
    for part in parts:
        if not part:
            continue
        if joined and not (_is_cjk(joined[-1]) or _is_cjk(part[0])):
            joined += " "
        joined += part
    joined = strip_markdown(joined)
    joined = re.sub(r"[ \t]{2,}", " ", joined)
    if _mojibake(joined):
        return ""
    return _clip(joined, width)


_NOISE = re.compile(r"^<system-reminder>|^</system-reminder>|^<\?xml|^<!DOCTYPE")


def _mojibake(line: str) -> bool:
    """True when a log line lost its encoding and is not worth showing."""
    bad = line.count("�")
    return bad >= 2 or (bad and bad >= len(line) * 0.1)


def clip_lines(lines: Sequence[str], max_lines: int, width: int) -> List[str]:
    """Clean + cap a block of output lines, keeping the head.

    Harness chatter (system reminders, xml prologs) is dropped so a demo never
    shows bookkeeping the audience cannot interpret.
    """
    out: List[str] = []
    skipping = False
    for raw in lines:
        for ln in clean(raw).split("\n"):
            ln = ln.replace("\t", "    ").rstrip()
            if not ln.strip():
                continue
            if skipping:
                if "</system-reminder>" in ln:
                    skipping = False
                continue
            if ln.lstrip().startswith("<system-reminder>"):
                if "</system-reminder>" not in ln:
                    skipping = True
                continue
            if _NOISE.match(ln.lstrip()):
                continue
            if _mojibake(ln):
                continue
            out.append(_clip(ln, width))
            if len(out) >= max_lines:
                return out
    return out


_ATTACH = re.compile(r"^#+\s*(.+?):\s*(\S+)$")


def _summarise_attachment(text: str) -> str:
    """Turn Codex's '# Files mentioned by the user' preamble into one line."""
    names = []
    for line in text.split("\n"):
        m = _ATTACH.match(line.strip())
        if m:
            names.append(os.path.basename(m.group(2).strip()))
    if not names:
        return ""
    return "attached " + ", ".join(names[:3])


def _arg_summary(name: str, args) -> str:
    """Short, human-readable argument hint for a tool call."""
    if not isinstance(args, dict):
        return ""
    keys = ("file_path", "path", "notebook_path", "pattern", "command", "cmd",
            "query", "url", "prompt", "code", "description", "title")
    for key in keys:
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return flatten(val, 56)
    return ""


def _tool_out_lines(payload) -> List[str]:
    """Normalise the many shapes a tool result can take into text lines."""
    if payload is None:
        return []
    if isinstance(payload, str):
        # Codex wraps tool output as a JSON envelope: {"output": "...", ...}
        head = payload.lstrip()[:1]
        if head in ("{", "["):
            try:
                inner = json.loads(payload)
            except (ValueError, TypeError):
                inner = None
            if isinstance(inner, (dict, list)):
                got = _tool_out_lines(inner)
                if got:
                    return got
        return payload.split("\n")
    if isinstance(payload, list):
        buf: List[str] = []
        for item in payload:
            if isinstance(item, str):
                buf.extend(item.split("\n"))
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    buf.extend(item["text"].split("\n"))
                else:
                    buf.append(json.dumps(item, ensure_ascii=False))
        return buf
    if isinstance(payload, dict):
        for key in ("stdout", "output", "content", "text", "result", "message"):
            if key in payload:
                got = _tool_out_lines(payload[key])
                if got:
                    return got
        return [json.dumps(payload, ensure_ascii=False)]
    return [str(payload)]


# --------------------------------------------------------------------------- #
# Claude Code
# --------------------------------------------------------------------------- #

def load_claude(path: str) -> List[Msg]:
    """Read a Claude Code session JSONL into normalised messages."""
    msgs: List[Msg] = []
    pending = {}          # tool_use_id -> index into msgs
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = rec.get("type")
            if kind not in ("user", "assistant"):
                continue
            if rec.get("isSidechain"):
                continue
            body = rec.get("message") or {}
            content = body.get("content")

            if kind == "user":
                # a plain string is a human turn; a list is usually tool results
                if isinstance(content, str):
                    if rec.get("isMeta"):
                        continue
                    text = flatten(content)
                    if text:
                        msgs.append(Msg(role="user", text=text))
                    continue
                for block in content or []:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text = flatten(block.get("text", ""))
                        if text:
                            msgs.append(Msg(role="user", text=text))
                    elif btype == "tool_result":
                        tid = block.get("tool_use_id")
                        idx = pending.pop(tid, None)
                        if idx is None:
                            continue
                        payload = block.get("content")
                        if payload is None:
                            payload = rec.get("toolUseResult")
                        msgs[idx].lines = _tool_out_lines(payload)
                        msgs[idx].error = bool(block.get("is_error"))
                continue

            for block in content or []:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    text = flatten(block.get("text", ""))
                    if text:
                        msgs.append(Msg(role="assistant", text=text))
                elif btype == "tool_use":
                    args = block.get("input") or {}
                    name = str(block.get("name", "tool"))
                    msgs.append(Msg(role="tool", tool=name,
                                    call=_arg_summary(name, args)))
                    if block.get("id"):
                        pending[block["id"]] = len(msgs) - 1
    return msgs


# --------------------------------------------------------------------------- #
# Codex CLI
# --------------------------------------------------------------------------- #

def load_codex(path: str) -> List[Msg]:
    """Read a Codex rollout JSONL into normalised messages."""
    msgs: List[Msg] = []
    pending = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "response_item":
                continue
            p = rec.get("payload") or {}
            ptype = p.get("type")

            if ptype == "message":
                role = p.get("role")
                if role not in ("user", "assistant"):
                    continue
                text = " ".join(
                    b.get("text", "") for b in (p.get("content") or [])
                    if isinstance(b, dict) and b.get("type") in
                    ("input_text", "output_text", "text")
                )
                flat = flatten(text)
                # Codex injects huge developer/user preambles; skip those
                if not flat or "AGENTS.md instructions" in flat:
                    continue
                if flat.startswith("<") and not flat.startswith("<turn_aborted>"):
                    continue
                if role == "user" and flat.startswith("#") and "Codex" not in flat:
                    pass
                if flat.startswith("# Files mentioned by the user"):
                    flat = _summarise_attachment(text) or flat
                if role == "user" and (rec.get("ordinal", 0) < 20 and len(flat) > 120):
                    continue
                msgs.append(Msg(role=role, text=flat))
            elif ptype == "function_call":
                name = str(p.get("name", "tool"))
                try:
                    args = json.loads(p.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                msgs.append(Msg(role="tool", tool=name, call=_arg_summary(name, args)))
                if p.get("call_id"):
                    pending[p["call_id"]] = len(msgs) - 1
            elif ptype == "function_call_output":
                idx = pending.pop(p.get("call_id"), None)
                if idx is not None:
                    msgs[idx].lines = _tool_out_lines(p.get("output"))
    return msgs


# --------------------------------------------------------------------------- #
# format detection
# --------------------------------------------------------------------------- #

def detect_format(path: str) -> str:
    """Return 'claude' or 'codex'; raise ValueError for unsupported input."""
    if path.endswith(".zst") or path.endswith(".zstd"):
        raise ValueError(
            "this session log is zstd-compressed and demo-reel bundles no zstd "
            "decoder; decompress it first, then convert the plain .jsonl"
        )
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for _ in range(40):
            raw = fh.readline()
            if not raw:
                break
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if rec.get("type") in ("session_meta", "event_msg", "world_state", "turn_context"):
                return "codex"
            if rec.get("type") in ("user", "assistant", "system", "summary") and "sessionId" in rec:
                return "claude"
    return "claude"


def load_session(path: str) -> List[Msg]:
    """Load either supported session format."""
    fmt = detect_format(path)
    if fmt == "codex":
        return load_codex(path)
    return load_claude(path)


# --------------------------------------------------------------------------- #
# TOML emission
# --------------------------------------------------------------------------- #

def _q(value: str) -> str:
    """Quote a Python string as a TOML basic string."""
    out = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _steps(msgs: Iterable[Msg], include_tools: bool = True) -> List[str]:
    lines: List[str] = []
    for m in msgs:
        if m.role == "user":
            lines.append("[[steps]]")
            lines.append("type = " + _q("user"))
            lines.append("label = " + _q("you"))
            lines.append("text = " + _q(m.text))
        elif m.role == "assistant":
            lines.append("[[steps]]")
            lines.append("type = " + _q("assistant"))
            lines.append("label = " + _q("claude"))
            lines.append("text = " + _q(m.text))
        elif m.role == "tool" and include_tools:
            lines.append("[[steps]]")
            lines.append("type = " + _q("tool"))
            lines.append("label = " + _q(m.tool))
            lines.append("call = " + _q(m.call))
            if m.lines:
                rendered = ", ".join(_q(x) for x in m.lines)
                lines.append("lines = [" + rendered + "]")
            if m.error:
                lines.append('out_style = "red"')
        else:
            continue
        lines.append("")
    return lines


def to_toml(
    msgs: Sequence[Msg],
    title: str = "session",
    theme: str = "dracula",
    width: int = 1600,
    height: int = 900,
    font_size: int = 24,
    fps: int = 30,
    chars_per_second: int = 60,
    gap_after_step: float = 0.28,
    output_delay: float = 0.03,
    lead_in: float = 0.5,
    tail: float = 1.4,
    include_tools: bool = True,
    banner: Optional[str] = None,
    line_width: int = 96,
    max_tool_lines: int = 4,
) -> str:
    """Render normalised messages as a complete demo-reel TOML document."""
    trimmed: List[Msg] = []
    for m in msgs:
        if m.role == "tool":
            trimmed.append(Msg(role="tool", tool=m.tool, call=m.call,
                               lines=clip_lines(m.lines, max_tool_lines, line_width),
                               error=m.error))
        else:
            trimmed.append(m)

    head = [
        "[meta]",
        "title = " + _q(title),
        "theme = " + _q(theme),
        "width = %d" % width,
        "height = %d" % height,
        "font_size = %d" % font_size,
        "fps = %d" % fps,
        "chars_per_second = %g" % chars_per_second,
        "output_delay = %g" % output_delay,
        "gap_after_step = %g" % gap_after_step,
        "lead_in = %g" % lead_in,
        "tail = %g" % tail,
        "",
    ]
    body: List[str] = []
    if banner:
        body.extend(["[[steps]]", "type = " + _q("banner"),
                     "text = " + _q(banner), "style = " + _q("blue"), ""])
    body.extend(_steps(trimmed, include_tools=include_tools))
    return "\n".join(head + body).rstrip() + "\n"


def convert(
    session: str,
    out: str,
    title: Optional[str] = None,
    theme: str = "dracula",
    include_tools: bool = True,
    banner: Optional[str] = None,
    **meta,
) -> str:
    """Convert a session log file into a TOML demo script on disk."""
    msgs = load_session(session)
    if not msgs:
        raise ValueError("no renderable messages found in %s" % session)
    if title is None:
        title = os.path.splitext(os.path.basename(session))[0]
    if banner is None:
        fmt = detect_format(session)
        agent = "claude-code" if fmt == "claude" else "codex"
        folder = os.path.basename(os.path.dirname(session))[:40]
        banner = "session  %s  %s  %s" % (_session_stamp(session), agent, folder)
    doc = to_toml(msgs, title=title, theme=theme,
                  include_tools=include_tools, banner=banner, **meta)
    parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(parent, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    return out


def _session_stamp(path: str) -> str:
    """Best-effort session date, so the banner looks like a real session."""
    try:
        first = ""
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for _ in range(30):
                line = fh.readline()
                if not line:
                    break
                if '"timestamp"' in line:
                    first = line
                    break
        pat = r'"timestamp"\s*:\s*"(\d{4}-\d{2}-\d{2})"';
        m = re.search(pat, first)
        if m:
            return m.group(1)
        import datetime
        return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    except Exception:
        return "0000-00-00"
