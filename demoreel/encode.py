"""Stream raw frames into ffmpeg (mp4 / gif)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Iterable, Optional


# Fallbacks for installs that do not touch PATH. No machine-specific paths:
# candidates are expanded per platform so the wheel stays portable.
_FALLBACKS = {
    "win32": (
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
    ),
    "darwin": ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"),
    "linux": ("/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/snap/bin/ffmpeg"),
}


def find_ffmpeg(explicit: Optional[str] = None) -> str:
    """Resolve an ffmpeg binary: explicit flag, then PATH, then common installs."""
    if explicit:
        return explicit
    for name in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(name)
        if found:
            return found
    import os
    for candidate in _FALLBACKS.get(sys.platform, ()):
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError(
        "ffmpeg not found. Install it (brew install ffmpeg / apt install ffmpeg / "
        "winget install Gyan.FFmpeg) or pass --ffmpeg /path/to/ffmpeg"
    )


def stream(frames: Iterable, width: int, height: int, fps: int, out: str,
           ffmpeg: Optional[str] = None, crf: int = 18, gif: bool = False,
           gif_width: int = 1200) -> str:
    exe = find_ffmpeg(ffmpeg)
    if gif:
        vf = (f"scale={gif_width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192[p];"
              f"[b][p]paletteuse=dither=bayer:bayer_scale=4")
        cmd = [exe, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
               "-r", str(fps), "-i", "-", "-vf", vf, "-loop", "0", out]
    else:
        cmd = [exe, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
               "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
               "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        for img in frames:
            proc.stdin.write(img.tobytes())
        proc.stdin.close()
    finally:
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed with code {rc}")
    return out


def probe(path: str, ffmpeg: Optional[str] = None) -> dict:
    exe = find_ffmpeg(ffmpeg)
    probe_exe = exe.replace("ffmpeg", "ffprobe")
    out = subprocess.run([probe_exe, "-v", "quiet", "-print_format", "json",
                          "-show_format", "-show_streams", path],
                         capture_output=True, text=True)
    import json
    try:
        return json.loads(out.stdout)
    except Exception:
        return {}
