"""Test suite for demo-reel.

Every test runs in a temporary directory and never touches a real session log
with write access: the session fixtures are synthesised JSONL that mirrors the
real record shapes (Claude Code and Codex), so the suite is deterministic and
works on machines with no agent history at all.

Run with:  python -m pytest tests -q     (or)     python tests/test_demoreel.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from demoreel import fonts, fromsession, script, term  # noqa: E402


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _write_jsonl(path: Path, records) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def claude_fixture(path: Path) -> Path:
    """A miniature Claude Code transcript: one prompt, one tool, one answer."""
    recs = [
        {"type": "mode", "mode": "normal", "sessionId": "s1"},
        {"type": "user", "sessionId": "s1", "uuid": "u1", "origin": {"kind": "human"},
         "timestamp": "2026-01-02T03:04:05.000Z",
         "message": {"role": "user", "content": "fix the failing test"}},
        {"type": "assistant", "sessionId": "s1", "uuid": "a1", "timestamp": "2026-01-02T03:04:06.000Z",
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": "Let me look at the test."},
             {"type": "tool_use", "id": "t1", "name": "Read",
              "input": {"file_path": "tests/test_api.py"}},
         ]}},
        {"type": "user", "sessionId": "s1", "uuid": "u2",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t1",
              "content": [{"type": "text", "text": "line one\nline two\nline three"}]},
         ]}},
        {"type": "assistant", "sessionId": "s1", "uuid": "a2",
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": "The assertion compares **strings** to ints."},
         ]}},
    ]
    return _write_jsonl(path, recs)


def codex_fixture(path: Path) -> Path:
    recs = [
        {"timestamp": "2026-01-02T03:04:05.000Z", "ordinal": 0, "type": "session_meta",
         "payload": {"session_id": "c1", "cwd": "C:/work"}},
        {"timestamp": "2026-01-02T03:04:06.000Z", "ordinal": 1, "type": "response_item",
         "payload": {"type": "message", "role": "developer",
                     "content": [{"type": "input_text", "text": "<app-context>ignore me</app-context>"}]}},
        {"timestamp": "2026-01-02T03:04:07.000Z", "ordinal": 2, "type": "response_item",
         "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "what api do you use"}]}},
        {"timestamp": "2026-01-02T03:04:08.000Z", "ordinal": 3, "type": "response_item",
         "payload": {"type": "function_call", "name": "exec_command", "call_id": "c-1",
                     "arguments": json.dumps({"cmd": "Get-Content SKILL.md"})}},
        {"timestamp": "2026-01-02T03:04:09.000Z", "ordinal": 4, "type": "response_item",
         "payload": {"type": "function_call_output", "call_id": "c-1",
                     "output": json.dumps({"output": "name: openai-docs", "metadata": {}})}},
        {"timestamp": "2026-01-02T03:04:10.000Z", "ordinal": 5, "type": "response_item",
         "payload": {"type": "message", "role": "assistant",
                     "content": [{"type": "output_text", "text": "I run on the OpenAI API."}]}},
    ]
    return _write_jsonl(path, recs)


# --------------------------------------------------------------------------- #
# text hygiene
# --------------------------------------------------------------------------- #

class TestTextHygiene(unittest.TestCase):
    def test_ansi_and_cr_are_stripped(self):
        raw = "\x1b[31mred\x1b[0m\r\nnext"
        self.assertEqual(fromsession.clean(raw), "red\nnext")

    def test_flatten_collapses_blank_lines(self):
        self.assertEqual(fromsession.flatten("a\n\n\nb"), "a b")

    def test_flatten_keeps_cjk_adjacent(self):
        # CJK has no inter-word space; inserting one would look like a typo
        self.assertEqual(fromsession.flatten("中文\n换行"), "中文换行")

    def test_flatten_truncates_by_cells_not_chars(self):
        wide = "\u4e2d" * 40           # 40 chars, 80 cells
        got = fromsession.flatten(wide, width=20)
        self.assertLessEqual(term.display_width(got), 20)
        self.assertTrue(got.endswith("\u2026"))

    def test_clip_lines_drops_system_reminder_blocks(self):
        lines = ["<system-reminder>noise", "more noise", "</system-reminder>", "real output"]
        self.assertEqual(fromsession.clip_lines(lines, 4, 80), ["real output"])

    def test_clip_lines_drops_mojibake(self):
        lines = ["\ufffd\ufffd\ufffd\ufffd broken", "good line"]
        self.assertEqual(fromsession.clip_lines(lines, 4, 80), ["good line"])

    def test_clip_lines_respects_max_lines(self):
        lines = [f"line {i}" for i in range(10)]
        self.assertEqual(len(fromsession.clip_lines(lines, 3, 80)), 3)

    def test_markdown_emphasis_is_removed(self):
        self.assertEqual(fromsession.strip_markdown("a **bold** and `code`"), "a bold and code")


# --------------------------------------------------------------------------- #
# width model
# --------------------------------------------------------------------------- #

class TestWidthModel(unittest.TestCase):
    def test_ascii_is_narrow(self):
        self.assertEqual(term.display_width("hello"), 5)

    def test_cjk_is_double(self):
        self.assertEqual(term.display_width("中文"), 4)

    def test_mixed(self):
        self.assertEqual(term.display_width("ab\u4e2d"), 4)

    def test_grid_reserves_two_cells_for_wide_glyph(self):
        g = term.Grid(10, 3)
        g.write("\u4e2d", term.Style())
        self.assertEqual(g.col, 2)
        self.assertIsNone(g.cells[0][1][0])

    def test_grid_wraps_before_splitting_a_wide_glyph(self):
        g = term.Grid(3, 3)
        g.write("ab", term.Style())
        g.put("\u4e2d", term.Style())     # would need cells 2 and 3 -> wrap
        self.assertEqual(g.row, 1)
        self.assertEqual(g.col, 2)

    def test_banner_pads_to_full_width(self):
        g = term.Grid(20, 2)
        g.banner("hi", term.Style())
        self.assertIn(g.cells[0][0][1].bg, ("caption_bg",))


# --------------------------------------------------------------------------- #
# session loading
# --------------------------------------------------------------------------- #

class TestClaudeSessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = claude_fixture(Path(self.tmp.name) / "s" / "abc.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_format_detected(self):
        self.assertEqual(fromsession.detect_format(str(self.path)), "claude")

    def test_messages_are_normalised(self):
        msgs = fromsession.load_claude(str(self.path))
        self.assertEqual([m.role for m in msgs], ["user", "assistant", "tool", "assistant"])

    def test_tool_output_is_attached_to_its_call(self):
        msgs = fromsession.load_claude(str(self.path))
        tool = [m for m in msgs if m.role == "tool"][0]
        self.assertEqual(tool.tool, "Read")
        self.assertEqual(tool.call, "tests/test_api.py")
        self.assertEqual(len(tool.lines), 3)

    def test_sidechain_and_meta_are_ignored(self):
        recs = [
            {"type": "user", "sessionId": "s", "isMeta": True,
             "message": {"role": "user", "content": "meta"}},
            {"type": "user", "sessionId": "s", "isSidechain": True,
             "message": {"role": "user", "content": "sub"}},
            {"type": "user", "sessionId": "s", "message": {"role": "user", "content": "real"}},
        ]
        p = _write_jsonl(Path(self.tmp.name) / "b.jsonl", recs)
        self.assertEqual([m.text for m in fromsession.load_claude(str(p))], ["real"])

    def test_error_results_are_flagged(self):
        recs = [
            {"type": "assistant", "sessionId": "s", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t9", "name": "Bash", "input": {"command": "false"}}]}},
            {"type": "user", "sessionId": "s", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t9", "is_error": True,
                 "content": "Exit code 1"}]}},
        ]
        p = _write_jsonl(Path(self.tmp.name) / "c.jsonl", recs)
        msgs = fromsession.load_claude(str(p))
        self.assertTrue(msgs[0].error)

    def test_to_toml_round_trips_through_the_parser(self):
        msgs = fromsession.load_claude(str(self.path))
        doc = fromsession.to_toml(msgs, title="demo")
        out = Path(self.tmp.name) / "demo.toml"
        out.write_text(doc, encoding="utf-8")
        demo = script.parse(str(out))
        self.assertGreater(len(demo.events), 0)
        self.assertGreater(demo.duration, 1.0)

    def test_quotes_and_backslashes_survive_toml(self):
        msgs = [fromsession.Msg(role="user", text='he said "hi" in C:\\temp')]
        out = Path(self.tmp.name) / "q.toml"
        out.write_text(fromsession.to_toml(msgs), encoding="utf-8")
        import tomllib
        with open(out, "rb") as fh:
            doc = tomllib.load(fh)
        self.assertEqual(doc["steps"][0]["text"], 'he said "hi" in C:\\temp')


class TestCodexSessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = codex_fixture(Path(self.tmp.name) / "r.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_format_detected(self):
        self.assertEqual(fromsession.detect_format(str(self.path)), "codex")

    def test_developer_preamble_is_dropped(self):
        msgs = fromsession.load_codex(str(self.path))
        self.assertNotIn("ignore me", " ".join(m.text for m in msgs))

    def test_function_call_pairs_with_its_output(self):
        msgs = fromsession.load_codex(str(self.path))
        tool = [m for m in msgs if m.role == "tool"][0]
        self.assertEqual(tool.tool, "exec_command")
        self.assertEqual(tool.call, "Get-Content SKILL.md")
        self.assertEqual(tool.lines, ["name: openai-docs"])

    def test_assistant_text_survives(self):
        msgs = fromsession.load_codex(str(self.path))
        self.assertTrue(any(m.role == "assistant" for m in msgs))


class TestUnsupportedSessions(unittest.TestCase):
    def test_zstd_log_is_rejected_with_a_useful_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "session.v4.jsonl.zstd"
            p.write_bytes(b"\x28\xb5\x2f\xfd")
            with self.assertRaises(ValueError) as ctx:
                fromsession.detect_format(str(p))
            self.assertIn("zstd", str(ctx.exception))

    def test_empty_session_is_rejected_by_convert(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.jsonl"
            p.write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                fromsession.convert(str(p), str(Path(tmp) / "o.toml"))


# --------------------------------------------------------------------------- #
# script parsing
# --------------------------------------------------------------------------- #

class TestScriptParsing(unittest.TestCase):
    def test_cmd_typing_produces_one_event_per_char(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "s.toml"
            p.write_text(
                '[meta]\nchars_per_second = 100\nprompt = ""\n'
                '[[steps]]\ntype = "cmd"\ntext = "echo hi"\n', encoding="utf-8")
            demo = script.parse(str(p))
            chars = [e for e in demo.events if e.kind == "char"]
            self.assertEqual(len(chars), len("echo hi") + 1)   # + newline

    def test_unknown_step_type_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.toml"
            p.write_text('[[steps]]\ntype = "nope"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                script.parse(str(p))

    def test_caption_window_is_clamped_to_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.toml"
            p.write_text(
                '[meta]\ntail = 0.1\n[[steps]]\ntype = "out"\nlines = ["x"]\n'
                'caption = "hello"\ncaption_hold = 99\n', encoding="utf-8")
            demo = script.parse(str(p))
            self.assertLessEqual(demo.captions[0].t1, demo.duration)


# --------------------------------------------------------------------------- #
# font discovery
# --------------------------------------------------------------------------- #

class TestFontDiscovery(unittest.TestCase):
    def test_explicit_paths_win(self):
        got = fonts.resolve(platform="linux", mono="/tmp/m.ttf", bold="/tmp/b.ttf",
                            cjk="/tmp/c.ttc")
        self.assertEqual(got["mono"], "/tmp/m.ttf")
        self.assertEqual(got["bold"], "/tmp/b.ttf")
        self.assertEqual(got["cjk"], "/tmp/c.ttc")
        self.assertEqual(got["cjk_bold"], "/tmp/c.ttc")   # falls back to the regular face

    def test_unknown_platform_returns_none_not_raises(self):
        got = fonts.resolve(platform="plan9")
        self.assertIsNone(got["mono"])
        self.assertIsNone(got["cjk"])

    def test_missing_platform_install_degrades_to_none(self):
        # a Linux box without DejaVu/Liberation still has to import cleanly
        self.assertIn("mono", fonts.resolve(platform="linux"))

    def test_renderer_survives_having_no_fonts(self):
        r = term.Renderer(width=320, height=200, font_size=12,
                          font_path=None, font_bold_path=None,
                          font_cjk=None, font_cjk_bold=None)
        img = r.frame(term.Grid(r.cols, r.rows))
        self.assertEqual(img.size, (320, 200))


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

class TestRendering(unittest.TestCase):
    def test_frame_is_the_requested_size(self):
        r = term.Renderer(width=640, height=360, font_size=16)
        img = r.frame(term.Grid(r.cols, r.rows))
        self.assertEqual(img.size, (640, 360))

    def test_chinese_text_changes_pixels(self):
        r = term.Renderer(width=640, height=360, font_size=16)
        blank = r.frame(term.Grid(r.cols, r.rows))
        g = term.Grid(r.cols, r.rows)
        g.line("\u4e2d\u6587", term.Style())
        self.assertNotEqual(blank.tobytes(), r.frame(g).tobytes())

    def test_caption_changes_pixels(self):
        r = term.Renderer(width=640, height=360, font_size=16)
        g = term.Grid(r.cols, r.rows)
        plain = r.frame(g)
        captioned = r.frame(g, caption="step one")
        self.assertNotEqual(plain.tobytes(), captioned.tobytes())

    def test_cursor_can_be_hidden(self):
        r = term.Renderer(width=640, height=360, font_size=16)
        g = term.Grid(r.cols, r.rows)
        self.assertNotEqual(r.frame(g, cursor_on=True).tobytes(),
                            r.frame(g, cursor_on=False).tobytes())

    def test_grid_scrolls_instead_of_growing(self):
        g = term.Grid(20, 3)
        for i in range(10):
            g.line(f"line {i}", term.Style())
        self.assertEqual(len(g.cells), 3)
        self.assertEqual(g.row, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
