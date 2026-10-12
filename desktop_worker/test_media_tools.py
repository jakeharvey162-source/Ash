import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from media_tools import export_video, status
from agent_runtime import AshAgentRuntime
from test_agent_runtime import FakeAgent


class MediaTests(unittest.TestCase):
    def test_missing_dependency_is_honest(self):
        with patch("media_tools.shutil.which", return_value=None):
            self.assertFalse(status()["available"])
            self.assertFalse(status()["generative_video"])

    def test_workspace_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                export_video(pathlib.Path(tmp), {"source": "../outside.mp4", "output": "out.mp4"})

    def test_agent_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = FakeAgent()
            agent.plan = {"steps": [{"tool": "media.video.export", "args": {"source": "clip.mp4", "output": "out.mp4"}}]}
            result = AshAgentRuntime(agent, pathlib.Path(tmp)).run("edit my clip")
            self.assertTrue(result.requires_confirmation)
            self.assertFalse((pathlib.Path(tmp) / "out.mp4").exists())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and ffprobe required")
    def test_real_export_preserves_audio_and_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:d=1",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libx264",
                            "-c:a", "aac", "-shortest", str(root / "source.mp4")], check=True)
            result = export_video(root, {"source": "source.mp4", "output": "edited.mp4", "duration": 0.5})
            self.assertGreater(result["bytes"], 0)
            import json
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json",
                                    str(root / "edited.mp4")], check=True, capture_output=True, text=True)
            streams = json.loads(probe.stdout)["streams"]
            video = next(s for s in streams if s["codec_type"] == "video")
            self.assertEqual((video["width"], video["height"]), (720, 1280))
            self.assertTrue(any(s["codec_type"] == "audio" for s in streams))
            for invalid in ({"duration": float("nan")}, {"preset": "unknown"}, {"duration": 121}):
                with self.assertRaises(ValueError):
                    export_video(root, {"source": "source.mp4", "output": "new.mp4", **invalid})
            with self.assertRaises(ValueError):
                export_video(root, {"source": "source.mp4", "output": "edited.mp4"})
