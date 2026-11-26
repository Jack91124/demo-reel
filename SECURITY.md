# Security policy

## Supported versions

demo-reel is pre-1.0; only the latest release receives fixes.

## Reporting

Open a private GitHub security advisory on
<https://github.com/Jack91124/demo-reel/security/advisories/new>, or email the maintainer listed on
the repository profile. Please do not open a public issue for a vulnerability.

## What demo-reel touches

Being honest about the attack surface, because "render a video" sounds harmless:

| Surface | Detail |
|---|---|
| **Session logs** | `from-session` reads a JSONL file you point it at. It is read-only: no writes, no network. It will contain whatever your transcript contains, including paths and snippets of code — the generated TOML is a plain-text summary, so **review it before committing**. |
| **ffmpeg subprocess** | The output path and codec flags are passed as an argument list, never through a shell. The binary is resolved from `PATH` or `--ffmpeg`; if you point `--ffmpeg` at an untrusted binary, that is on you. |
| **TOML scripts** | Parsed with `tomllib` (no code execution). A script can choose colours, text and timing — nothing else. There is no `exec`, no shell step, no plugin loading. |
| **Fonts** | Opened from local paths. A malicious font file is a font-rendering risk in Pillow, not a demo-reel-specific one. |
| **Network** | demo-reel makes **no network requests** at runtime. |

## Out of scope

- Rendering a transcript that contains secrets — the tool cannot know; redact your own demo input.
- Harms that require an already-compromised `ffmpeg` or `Pillow` installation.
