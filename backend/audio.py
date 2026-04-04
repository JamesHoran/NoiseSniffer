import queue
import time
import numpy as np
import sounddevice as sd
from collections import deque

SAMPLE_RATE = 44100
BLOCK_SIZE = 512

NOISE_AMPLITUDE = 0.08       # base white noise level
TONE_AMPLITUDE = 0.15        # per-packet sine burst level
DISTORTION_THRESHOLD = 50    # packets/sec before distortion kicks in


def _freq_for_packet(parsed: dict) -> float:
    """Map a parsed packet to a sine burst frequency."""
    protocol = parsed.get("protocol", "")
    dst_port = parsed.get("dst_port") or 0
    if protocol == "TCP":
        return 600 + (dst_port % 2400)   # 600–3000 Hz
    elif protocol == "UDP":
        return 200 + (dst_port % 400)    # 200–600 Hz
    elif protocol == "ICMP":
        return 120
    return 300


class _Tone:
    """Short sine burst with a linear attack/decay envelope."""
    ATTACK_S = 0.01   # 10 ms
    DECAY_S  = 0.25   # 250 ms

    def __init__(self, frequency: float):
        self.attack = int(SAMPLE_RATE * self.ATTACK_S)
        self.decay  = int(SAMPLE_RATE * self.DECAY_S)
        self.total  = self.attack + self.decay
        self._freq  = frequency
        self._pos   = 0
        self._phase = 0.0

    def render(self, frames: int) -> tuple[np.ndarray, bool]:
        """Return `frames` samples and whether this tone is finished."""
        n = min(frames, self.total - self._pos)

        phase_step = 2 * np.pi * self._freq / SAMPLE_RATE
        phases = self._phase + np.arange(n) * phase_step
        sine = np.sin(phases) * TONE_AMPLITUDE

        # Linear attack then linear decay
        pos_idx = self._pos + np.arange(n)
        env = np.where(
            pos_idx < self.attack,
            pos_idx / self.attack,
            1.0 - (pos_idx - self.attack) / self.decay,
        ).clip(0.0, 1.0)

        out = np.zeros(frames, dtype=np.float32)
        out[:n] = (sine * env).astype(np.float32)

        self._phase = float(phases[-1]) + phase_step if n > 0 else self._phase
        self._pos += n
        return out, self._pos >= self.total


class AudioEngine:
    def __init__(self):
        # SimpleQueue is lock-free and safe to write from any thread.
        self._new_tones: queue.SimpleQueue[_Tone] = queue.SimpleQueue()
        self._new_timestamps: queue.SimpleQueue[float] = queue.SimpleQueue()
        # These are only touched inside the audio callback thread.
        self._active_tones: list[_Tone] = []
        self._packet_times: deque[float] = deque()
        self._stream: sd.OutputStream | None = None

    def start(self):
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=BLOCK_SIZE,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()

    def on_packet(self, parsed: dict):
        """Feed a parsed packet into the audio engine. Safe to call from any thread."""
        self._new_tones.put(_Tone(_freq_for_packet(parsed)))
        self._new_timestamps.put(time.monotonic())

    def _callback(self, outdata, frames, time_info, status):
        """Called by sounddevice on its own audio thread to fill each output buffer."""

        # Drain any new tones queued since the last callback.
        while not self._new_tones.empty():
            self._active_tones.append(self._new_tones.get_nowait())

        # Update the rolling 1-second packet rate window.
        now = time.monotonic()
        while not self._new_timestamps.empty():
            self._packet_times.append(self._new_timestamps.get_nowait())
        while self._packet_times and now - self._packet_times[0] > 1.0:
            self._packet_times.popleft()

        # Base white noise layer.
        signal = (np.random.randn(frames) * NOISE_AMPLITUDE).astype(np.float32)

        # Mix in active tone bursts, removing finished ones.
        dead = []
        for i, tone in enumerate(self._active_tones):
            samples, done = tone.render(frames)
            signal += samples
            if done:
                dead.append(i)
        for i in reversed(dead):
            self._active_tones.pop(i)

        # Waveshaping distortion when packet rate exceeds the threshold.
        rate = len(self._packet_times)
        if rate > DISTORTION_THRESHOLD:
            excess = min((rate - DISTORTION_THRESHOLD) / DISTORTION_THRESHOLD, 1.0)
            gain = 1.0 + excess * 4.0  # up to 5× gain at peak
            signal = np.tanh(signal * gain)

        outdata[:, 0] = np.clip(signal, -1.0, 1.0)


engine = AudioEngine()
