"""Parse a TOML demo script into a timed event stream.

Two script flavours share one timeline:

  * terminal mode  -- cmd / out / clear / pause
  * agent mode     -- user / assistant / tool

Both produce the same flat event list, so rendering, captions and encoding are
identical for the two.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Event:
    t: float
    kind: str            # char | line | clear | banner
    payload: object
    style: dict = field(default_factory=dict)


@dataclass
class Caption:
    t0: float
    t1: float
    text: str


@dataclass
class Demo:
    meta: dict
    events: List[Event]
    captions: List[Caption]
    duration: float


def _style(v) -> dict:
    if v is None:
        return {}
    if isinstance(v, str):
        return {"fg": v}
    return dict(v)


def _typing(events, t, text, style, cps, mult=1.0):
    for ch in text:
        events.append(Event(t, "char", ch, dict(style)))
        t += 1.0 / max(cps * mult, 1.0)
    return t


def parse(path: str) -> Demo:
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    meta = doc.get("meta", {})
    cps = float(meta.get("chars_per_second", 30))
    out_delay = float(meta.get("output_delay", 0.055))
    gap = float(meta.get("gap_after_step", 0.55))

    events: List[Event] = []
    captions: List[Caption] = []
    t = float(meta.get("lead_in", 0.55))

    for step in doc.get("steps", []):
        kind = step.get("type", "cmd")
        cap = step.get("caption")

        if kind == "clear":
            events.append(Event(t, "clear", None))
            t += gap * 0.5
            continue
        if kind == "pause":
            t += float(step.get("seconds", 1.0))
            continue

        if kind == "cmd":
            prefix = step.get("prompt", meta.get("prompt", "~ $ "))
            if prefix:
                t = _typing(events, t, prefix, _style(step.get("prompt_style", meta.get("prompt_style", "green"))), cps, 1.7)
            t = _typing(events, t, step["text"], _style(step.get("style", meta.get("cmd_style"))), cps)
            if step.get("enter", True):
                events.append(Event(t, "char", "\n", {}))
                t += out_delay
        elif kind == "out":
            style = _style(step.get("style"))
            for ln in step.get("lines", []):
                events.append(Event(t, "line", ln, dict(style)))
                t += float(step.get("delay", out_delay))
        elif kind == "banner":
            events.append(Event(t, "banner", step.get("text", ""), _style(step.get("style"))))
            t += out_delay
        elif kind == "user":
            label = step.get("label", "you")
            t = _typing(events, t, f"{label}  ", _style(step.get("label_style", "purple")), cps, 2.2)
            events.append(Event(t, "line", step["text"], _style(step.get("style", "fg"))))
            t += out_delay
        elif kind == "assistant":
            label = step.get("label", "agent")
            t = _typing(events, t, f"{label}  ", _style(step.get("label_style", "green")), cps, 2.2)
            events.append(Event(t, "line", step["text"], _style(step.get("style", "fg"))))
            t += out_delay
        elif kind == "tool":
            label = step.get("label", "tool")
            head = step.get("call", "")
            t = _typing(events, t, f"  {label} {head}", _style(step.get("style", "dim")), cps, 1.6)
            events.append(Event(t, "char", "\n", {}))
            t += out_delay
            for ln in step.get("lines", []):
                events.append(Event(t, "line", "    " + ln, _style(step.get("out_style", "dim"))))
                t += out_delay * 0.8
        else:
            raise ValueError(f"unknown step type: {kind!r}")

        if cap:
            captions.append(Caption(t, t + float(step.get("caption_hold", 2.2)), cap))
        t += gap

    duration = max(t + float(meta.get("tail", 1.1)), 2.0)
    for c in captions:
        c.t1 = min(c.t1, duration)
    return Demo(meta=meta, events=events, captions=captions, duration=duration)


def caption_at(demo: Demo, t: float) -> Optional[str]:
    for c in demo.captions:
        if c.t0 <= t < c.t1:
            return c.text
    return None
