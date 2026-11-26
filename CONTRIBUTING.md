# Contributing to demo-reel

Thanks for looking. This project is deliberately small — one renderer, one parser, no browser — so
the bar for a useful contribution is low and the review is fast.

## Good first issues

- **Add a session format.** `demoreel/fromsession.py` has `load_claude()` and `load_codex()`;
  each is one function returning `List[Msg]`. Gemini CLI, Cursor and OpenCode all write JSONL-ish
  transcripts. Add `load_<tool>()`, teach `detect_format()` the first-record shape, and add
  fixtures to `tests/test_demoreel.py` (synthesise them — never commit a real transcript).
- **Add a theme.** `demoreel/themes.py` — one dict of 19 colour keys.
- **Auto poster frame.** Pick the frame with the most ink and write it as `--poster out.png`.
- **Font discovery.** Right now the Windows path list is hard-coded; a proper
  `platform`-aware font finder with a graceful fallback would help a lot of first-time users.

## Ground rules

1. **No screen recording, no browser.** The whole point of the project is that frames are drawn,
   not captured. A PR that shells out to Chrome will be declined politely.
2. **Determinism.** Rendering the same script twice must produce identical frames. No `random`,
   no wall-clock time inside the render loop, no "try again and see."
3. **Tests run offline.** Every test must pass on a machine with no agent history, no network and
   no fonts beyond what `Pillow` finds. Session fixtures are generated, not copied.
4. **Don't widen the dependency surface.** Runtime deps are `pillow` and the `ffmpeg` binary.
   A feature that needs three new packages needs a very good argument.
5. **Text, not data.** Anything a user would want to review in a diff belongs in the TOML script,
   not in a pickled blob.

## Workflow

```bash
git clone https://github.com/Jack91124/demo-reel
cd demo-reel
python -m pip install -e ".[dev]"
python -m pytest tests -q              # 39 tests, under a second

# try your change against a real render
python -m demoreel render demos/aem.toml -o out/scratch.mp4 --quiet
```

Before opening a PR:

- `python -m pytest tests -q` is green
- `python -m compileall -q demoreel tests` is silent
- if you touched rendering, attach a still (`demoreel still … -o shot.png`) to the PR description
  so reviewers can see it without rendering anything

Commit messages: plain imperative, one line, e.g. `fromsession: pair codex tool output envelopes`.

## Reporting bugs

Useful report = the script that reproduces it + the command you ran + Python version + OS +
whether ffmpeg is on `PATH`. If the bug is visual, a still PNG is worth a thousand words.

Security issues: please open a private advisory rather than a public issue.

## License

By contributing you agree your work is released under the MIT license.
