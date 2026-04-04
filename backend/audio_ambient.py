"""
Ambient audio engine using real MP3 samples for network sonification.

Uses miniaudio to decode MP3 files at startup and plays them back
through the existing sounddevice stream when network packets arrive.
"""
import queue
import threading
from collections import deque
from pathlib import Path
from typing import Literal

import numpy as np
import sounddevice as sd
import miniaudio

SAMPLE_RATE = 44100
BLOCK_SIZE = 512

FFT_SIZE = 2048
NUM_BINS = 1024
SPECTRUM_INTERVAL = SAMPLE_RATE // 30
DB_MIN, DB_MAX = -60.0, 0.0

_HANN = np.hanning(FFT_SIZE)

# Ambient sound types that map to directories
AmbientType = Literal[
    "rain", "wind", "fire", "forest", "drones", "hospital_beep"
]

# Directory mapping for ambient sounds (relative to backend directory)
AUDIO_DIRS = {
    "rain": "../audio/Rain",
    "wind": "../audio/Wind",
    "fire": "../audio/Fire",
    "forest": "../audio/Forrest",
    "drones": "../audio/Drones",
    "hospital_beep": "../audio/Hospital Beep",
}

# Cache for loaded audio samples
_loaded_samples: dict[str, np.ndarray] = {}
_sample_lock = threading.Lock()


def _list_audio_files(directory: str) -> list[Path]:
    """List all MP3 files in a directory."""
    path = Path(directory)
    if not path.exists():
        return []
    return list(path.glob("*.mp3"))


def _load_mp3(file_path: Path) -> np.ndarray:
    """Load an MP3 file and return as mono float32 numpy array."""
    decoded = miniaudio.decode_file(str(file_path))

    # Convert to numpy array (int16 -> float32)
    samples = np.array(decoded.samples, dtype=np.float32) / 32768.0

    # Convert stereo to mono by averaging channels
    if decoded.nchannels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)

    # Resample to our sample rate if needed
    if decoded.sample_rate != SAMPLE_RATE:
        # Simple resampling using linear interpolation
        from scipy import signal
        num_samples = int(len(samples) * SAMPLE_RATE / decoded.sample_rate)
        samples = signal.resample(samples, num_samples)

    return samples.astype(np.float32)


def _get_ambient_sample(sound_type: str) -> np.ndarray:
    """Get or load an ambient sound sample for the given type."""
    with _sample_lock:
        if sound_type in _loaded_samples:
            return _loaded_samples[sound_type]

        # Find the audio directory
        dir_name = AUDIO_DIRS.get(sound_type.lower())
        if not dir_name:
            print(f"[audio] Unknown sound type '{sound_type}', defaulting to 'rain'")
            dir_name = AUDIO_DIRS["rain"]

        # List available files
        files = _list_audio_files(dir_name)
        if not files:
            print(f"[audio] No MP3 files found in {dir_name}")
            # Return silence
            return np.zeros(int(SAMPLE_RATE * 2), dtype=np.float32)

        # Load the first file (we could randomize or round-robin)
        sample = _load_mp3(files[0])
        _loaded_samples[sound_type] = sample
        print(f"[audio] Loaded {sound_type} from {files[0].name} ({len(sample)} samples)")
        return sample


def _compute_spectrum(samples: np.ndarray) -> list[float]:
    magnitude = np.abs(np.fft.rfft(samples * _HANN)) / FFT_SIZE
    db = 20 * np.log10(magnitude + 1e-10)
    normalised = np.clip((db - DB_MIN) / (DB_MAX - DB_MIN), 0.0, 1.0)
    return normalised[:NUM_BINS].tolist()


class AmbientTone:
    """A playing ambient sound with position tracking."""

    def __init__(self, samples: np.ndarray, boost: float = 1.0):
        self._samples = samples * boost
        self._pos = 0
        self._length = len(samples)

    def render(self, frames: int) -> tuple[np.ndarray, bool]:
        """Render up to `frames` samples of the ambient sound."""
        if self._pos >= self._length:
            return np.zeros(frames, dtype=np.float32), True

        n = min(frames, self._length - self._pos)
        audio = self._samples[self._pos:self._pos + n]

        # Fade out the last 10% to avoid clicks
        fade_start = max(0, self._length - int(self._length * 0.1))
        if self._pos >= fade_start:
            fade_pos = self._pos - fade_start
            fade_len = self._length - fade_start
            fade = 1.0 - (fade_pos / fade_len)
            audio *= fade

        out = np.zeros(frames, dtype=np.float32)
        out[:n] = audio
        self._pos += n
        return out, self._pos >= self._length


class AudioEngine:
    def __init__(self):
        self._new_tones: queue.SimpleQueue = queue.SimpleQueue()
        self._active_tones: list = []
        self._stream: sd.OutputStream | None = None
        self._rules: dict[int, dict] = {}
        self._muted: bool = False
        self._sample_buffer: deque[float] = deque(maxlen=FFT_SIZE)
        self._samples_since_spectrum: int = 0
        self.latest_spectrum: list[float] | None = None

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

    def set_muted(self, muted: bool):
        self._muted = muted

    def update_rules(self, rules: dict[int, dict]):
        print(f"[audio_engine] update_rules called with {len(rules)} rule(s): {list(rules.keys())}")
        self._rules = rules
        for port, rule in rules.items():
            sound_type = rule.get('sound_type', 'rain')
            boost = rule.get('frequency_boost', 1.0)
            print(f"[audio_engine]   Port {port}: sound={sound_type}, boost={boost}")
        print(f"[rules] {len(rules)} rule(s) active — ports: {list(rules.keys())}")

    def on_packet(self, parsed: dict):
        dst_port = parsed.get("dst_port") or 0
        src_ip = parsed.get("src_ip", "")
        rule = self._rules.get(dst_port)

        if rule:
            whitelist = rule.get("ip_whitelist", [])
            if whitelist and src_ip not in whitelist:
                rule = None

        if not rule:
            return

        sound_type = rule.get("sound_type", "rain")
        boost = rule.get("frequency_boost", 1.0)

        # Get the ambient sample for this sound type
        samples = _get_ambient_sample(sound_type)

        print(f"[rule hit] port={dst_port} sound={sound_type} boost={boost}")
        self._new_tones.put(AmbientTone(samples, boost))

    def _callback(self, outdata, frames, time_info, status):
        if self._muted:
            outdata[:] = 0
            return

        while not self._new_tones.empty():
            self._active_tones.append(self._new_tones.get_nowait())

        signal = np.zeros(frames, dtype=np.float32)

        dead = []
        for i, tone in enumerate(self._active_tones):
            samples, done = tone.render(frames)
            signal += samples
            if done:
                dead.append(i)
        for i in reversed(dead):
            self._active_tones.pop(i)

        outdata[:, 0] = np.clip(signal, -1.0, 1.0)

        self._sample_buffer.extend(outdata[:, 0].tolist())
        self._samples_since_spectrum += frames
        if self._samples_since_spectrum >= SPECTRUM_INTERVAL and len(self._sample_buffer) == FFT_SIZE:
            self.latest_spectrum = _compute_spectrum(np.array(self._sample_buffer, dtype=np.float32))
            self._samples_since_spectrum = 0


engine = AudioEngine()
