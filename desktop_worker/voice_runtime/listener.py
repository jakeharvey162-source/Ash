from __future__ import annotations

import os
import time
from collections import deque
from .wake import WakeMatcher

class LocalWhisperListener:
    """Desktop-only local microphone listener using faster-whisper."""

    def __init__(self) -> None:
        self.sample_rate = int(os.environ.get("ASH_VOICE_SAMPLE_RATE", "16000"))
        self.block_ms = int(os.environ.get("ASH_VOICE_BLOCK_MS", "30"))
        self.block_samples = int(self.sample_rate * self.block_ms / 1000)
        self.silence_hangover_ms = int(os.environ.get("ASH_VOICE_SILENCE_MS", "850"))
        self.max_utterance_s = float(os.environ.get("ASH_VOICE_MAX_UTTERANCE_S", "20"))
        self.whisper_model_size = os.environ.get("ASH_WHISPER_MODEL", "small.en")
        self.input_device = os.environ.get("ASH_INPUT_DEVICE") or None
        self.wake = WakeMatcher()
        self._model = None
        self._silence_rms = 250.0

    @staticmethod
    def _deps():
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Local voice dependencies are not installed. Install "
                "desktop_worker/requirements-voice.optional.txt."
            ) from exc
        return np, sd, WhisperModel

    def _get_model(self):
        if self._model is None:
            _, _, WhisperModel = self._deps()
            self._model = WhisperModel(
                self.whisper_model_size,
                device=os.environ.get("ASH_WHISPER_DEVICE", "cpu"),
                compute_type=os.environ.get("ASH_WHISPER_COMPUTE", "int8"),
                cpu_threads=os.cpu_count() or 4,
            )
        return self._model

    def preload(self) -> None:
        self._get_model()

    def _rms(self, block) -> float:
        np, _, _ = self._deps()
        return float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))

    def _calibrate(self, stream, seconds: float = 0.8) -> float:
        np, _, _ = self._deps()
        levels = []
        for _ in range(max(1, int(seconds * 1000 / self.block_ms))):
            block, _ = stream.read(self.block_samples)
            levels.append(self._rms(block[:, 0]))
        baseline = float(np.median(levels)) if levels else 100.0
        return min(max(baseline * 3.0, 90.0), 500.0)

    def _record_utterance(self, stream):
        np, _, _ = self._deps()
        preroll = deque(maxlen=max(1, 300 // self.block_ms))
        chunks = []
        started = False
        silence_ms = 0
        start_time = time.time()
        while True:
            block, _ = stream.read(self.block_samples)
            mono = block[:, 0]
            level = self._rms(mono)
            if level > self._silence_rms:
                if not started:
                    chunks.extend(preroll)
                started = True
                silence_ms = 0
                chunks.append(mono.copy())
            elif started:
                silence_ms += self.block_ms
                chunks.append(mono.copy())
                if silence_ms >= self.silence_hangover_ms:
                    break
            else:
                preroll.append(mono.copy())
            if started and time.time() - start_time > self.max_utterance_s:
                break
            if not started and time.time() - start_time > 30:
                return np.array([], dtype=np.int16)
        return np.concatenate(chunks) if chunks else np.array([], dtype=np.int16)

    def _transcribe(self, audio) -> str:
        np, _, _ = self._deps()
        if audio.size < self.sample_rate * 0.35:
            return ""
        audio_f32 = audio.astype(np.float32) / 32768.0
        segments, _ = self._get_model().transcribe(
            audio_f32,
            language=os.environ.get("ASH_WHISPER_LANGUAGE", "en"),
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def listen_for_command(self, on_wake=None, on_heard=None) -> str:
        _, sd, _ = self._deps()
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.block_samples,
            device=self.input_device,
        ) as stream:
            self._silence_rms = self._calibrate(stream)
            while True:
                audio = self._record_utterance(stream)
                if getattr(audio, "size", 0) == 0:
                    continue
                text = self._transcribe(audio)
                if not text:
                    continue
                if on_heard:
                    on_heard(text)
                match = self.wake.find(text)
                if not match:
                    continue
                if on_wake:
                    on_wake()
                command = self.wake.command_after(text, match)
                if command:
                    return command
                follow_up = self._record_utterance(stream)
                follow_text = self._transcribe(follow_up)
                if follow_text:
                    if on_heard:
                        on_heard(follow_text)
                    return follow_text
