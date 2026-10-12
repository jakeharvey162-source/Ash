"""Local, no-API video exports. FFmpeg must be installed separately."""
from __future__ import annotations

import math
import pathlib
import shutil
import subprocess
import tempfile


def status():
    return {"engine": "ffmpeg", "available": bool(shutil.which("ffmpeg")),
            "api_required": False, "generative_video": False,
            "presets": ["vertical", "square", "landscape"]}


def export_video(root: pathlib.Path, args: dict):
    root = root.resolve()
    def path(key):
        raw = str(args.get(key) or "")
        if not raw:
            raise ValueError(f"{key} is required")
        result = (root / raw).resolve()
        if not result.is_relative_to(root):
            raise ValueError("Media must remain inside the Ash workspace")
        return result
    source, output = path("source"), path("output")
    if not source.is_file() or source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise ValueError("source must be an existing local video")
    if output.suffix.lower() != ".mp4" or output.exists():
        raise ValueError("output must be a new MP4 file")
    start, duration = float(args.get("start", 0)), float(args.get("duration", 30))
    if not all(math.isfinite(x) for x in (start, duration)) or start < 0 or not 0.1 <= duration <= 120:
        raise ValueError("Use a nonnegative start and duration between 0.1 and 120 seconds")
    sizes = {"vertical": (720, 1280), "square": (720, 720), "landscape": (1280, 720)}
    preset = args.get("preset", "vertical")
    if preset not in sizes:
        raise ValueError("Unknown video preset")
    engine = shutil.which("ffmpeg")
    if not engine:
        raise RuntimeError("Install FFmpeg on this desktop to enable video exports")
    width, height = sizes[preset]
    filters = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ash-video-", dir=output.parent) as tmp:
        rendered = pathlib.Path(tmp) / "render.mp4"
        command = [engine, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe", "-ss", str(start),
                   "-i", str(source), "-t", str(duration), "-map", "0:v:0", "-map", "0:a?",
                   "-vf", filters, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(rendered)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if completed.returncode or not rendered.is_file() or rendered.stat().st_size == 0:
            raise RuntimeError("FFmpeg could not export this video: " + completed.stderr[-1500:])
        # Exclusive creation prevents overwriting a file created during rendering.
        with output.open("xb") as target, rendered.open("rb") as stream:
            shutil.copyfileobj(stream, target)
    return {"output": str(output.relative_to(root)), "bytes": output.stat().st_size,
            "preset": preset, "requested_duration": duration, "engine": "ffmpeg"}
