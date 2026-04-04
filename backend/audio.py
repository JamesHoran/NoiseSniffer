"""
Audio engine for network sonification with multiple instruments.

Uses additive synthesis with different waveforms and envelopes to create
distinct instrument sounds without external dependencies.
"""
import queue
from collections import deque
from typing import Literal

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100
BLOCK_SIZE = 512

NOISE_AMPLITUDE = 0.08
TONE_AMPLITUDE = 0.4

FFT_SIZE = 2048
NUM_BINS = 1024
SPECTRUM_INTERVAL = SAMPLE_RATE // 30
DB_MIN, DB_MAX = -60.0, 0.0

_HANN = np.hanning(FFT_SIZE)

# Musical note → frequency (Hz)
NOTES: dict[str, float] = {
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61,
    "G3": 196.00, "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23,
    "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46,
    "G5": 783.99, "A5": 880.00, "B5": 987.77,
}
DEFAULT_NOTE = "A4"

# Supported instrument types
InstrumentType = Literal["piano", "guitar", "flute", "trumpet", "bells", "chiptune", "synth"]

# Instrument configurations
INSTRUMENTS = {
    "piano": {
        "waveform": "sine",
        "harmonics": [(1.0, 1.0), (2.0, 0.6), (3.0, 0.3), (4.0, 0.2), (5.0, 0.1)],
        "attack": 0.005,
        "decay": 0.05,
        "sustain": 0.3,
        "release": 0.5,
    },
    "guitar": {
        "waveform": "triangle",
        "harmonics": [(1.0, 1.0), (2.0, 0.8), (3.0, 0.6), (4.0, 0.4)],
        "attack": 0.001,
        "decay": 0.3,
        "sustain": 0.1,
        "release": 0.3,
    },
    "flute": {
        "waveform": "sine",
        "harmonics": [(1.0, 1.0), (2.0, 0.1), (3.0, 0.05)],
        "attack": 0.05,
        "decay": 0.1,
        "sustain": 0.7,
        "release": 0.2,
    },
    "trumpet": {
        "waveform": "sawtooth",
        "harmonics": [(1.0, 1.0), (2.0, 0.7), (3.0, 0.5), (4.0, 0.3), (5.0, 0.2)],
        "attack": 0.03,
        "decay": 0.1,
        "sustain": 0.8,
        "release": 0.15,
    },
    "bells": {
        "waveform": "sine",
        "harmonics": [(1.0, 1.0), (2.3, 0.6), (5.4, 0.4), (7.1, 0.2)],  # Inharmonic
        "attack": 0.001,
        "decay": 0.5,
        "sustain": 0.0,
        "release": 2.0,
    },
    "chiptune": {
        "waveform": "square",
        "harmonics": [(1.0, 1.0)],
        "attack": 0.001,
        "decay": 0.1,
        "sustain": 0.5,
        "release": 0.1,
    },
    "synth": {
        "waveform": "sawtooth",
        "harmonics": [(1.0, 0.8), (2.0, 0.6), (3.0, 0.4), (4.0, 0.3)],
        "attack": 0.02,
        "decay": 0.1,
        "sustain": 0.6,
        "release": 0.3,
    },
}


def _note_to_freq(note: str) -> float:
    return NOTES.get(note, NOTES[DEFAULT_NOTE])


def _compute_spectrum(samples: np.ndarray) -> list[float]:
    magnitude = np.abs(np.fft.rfft(samples * _HANN)) / FFT_SIZE
    db = 20 * np.log10(magnitude + 1e-10)
    normalised = np.clip((db - DB_MIN) / (DB_MAX - DB_MIN), 0.0, 1.0)
    return normalised[:NUM_BINS].tolist()


def _generate_waveform(freq: float, frames: int, phase: float, waveform: str, harmonics: list) -> tuple[np.ndarray, float]:
    """Generate audio samples for a specific waveform with harmonics."""
    t = np.arange(frames) / SAMPLE_RATE

    if waveform == "sine":
        # Sine wave with harmonics
        audio = np.zeros(frames, dtype=np.float32)
        for ratio, amp in harmonics:
            audio += np.sin(2 * np.pi * freq * ratio * t + phase * ratio) * amp
        audio /= len(harmonics)

    elif waveform == "square":
        # Square wave approximation (add odd harmonics with decreasing amplitude)
        audio = np.zeros(frames, dtype=np.float32)
        for n in range(1, 20, 2):  # Odd harmonics: 1, 3, 5, ...
            amp = 1.0 / n
            audio += np.sin(2 * np.pi * freq * n * t + phase * n) * amp
        audio *= 0.7  # Scale down slightly

    elif waveform == "sawtooth":
        # Sawtooth wave approximation (all harmonics with decreasing amplitude)
        audio = np.zeros(frames, dtype=np.float32)
        for n in range(1, 15):
            amp = 1.0 / n
            audio += np.sin(2 * np.pi * freq * n * t + phase * n) * amp
        audio *= 0.7

    elif waveform == "triangle":
        # Triangle wave approximation (odd harmonics with alternating sign)
        audio = np.zeros(frames, dtype=np.float32)
        for n in range(1, 15, 2):
            amp = (1.0 / (n * n)) * (1 if n % 4 == 1 else -1)
            audio += np.sin(2 * np.pi * freq * n * t + phase * n) * amp
        audio *= 2.0

    else:
        audio = np.sin(2 * np.pi * freq * t + phase)

    new_phase = (phase + 2 * np.pi * freq * frames / SAMPLE_RATE) % (2 * np.pi)
    return audio.astype(np.float32), new_phase


class InstrumentTone:
    """A single note event using configurable instrument synthesis."""

    def __init__(self, freq: float, instrument: str = "piano", boost: float = 1.0):
        if instrument not in INSTRUMENTS:
            print(f"[audio] Unknown instrument '{instrument}', using 'piano'")
            instrument = "piano"

        config = INSTRUMENTS[instrument]
        self._freq = freq
        self._amp = TONE_AMPLITUDE * boost
        self._waveform = config["waveform"]
        self._harmonics = config["harmonics"]
        self._phase = 0.0

        # Envelope parameters
        self._attack_len = int(SAMPLE_RATE * config["attack"])
        self._decay_len = int(SAMPLE_RATE * config["decay"])
        self._sustain_level = config["sustain"]
        self._release_len = int(SAMPLE_RATE * config["release"])
        self._total_len = self._attack_len + self._decay_len + self._release_len
        self._pos = 0

    def render(self, frames: int) -> tuple[np.ndarray, bool]:
        """Render up to `frames` samples of the instrument tone."""
        n = min(frames, self._total_len - self._pos)
        if n <= 0:
            return np.zeros(frames, dtype=np.float32), True

        # Generate envelope
        pos_indices = self._pos + np.arange(n)
        envelope = np.zeros(n, dtype=np.float32)

        # Attack phase
        attack_mask = pos_indices < self._attack_len
        envelope[attack_mask] = pos_indices[attack_mask] / self._attack_len

        # Decay phase
        decay_end = self._attack_len + self._decay_len
        decay_mask = (pos_indices >= self._attack_len) & (pos_indices < decay_end)
        if np.any(decay_mask):
            decay_pos = pos_indices[decay_mask] - self._attack_len
            envelope[decay_mask] = self._sustain_level + (1 - self._sustain_level) * np.exp(-5 * decay_pos / self._decay_len)

        # Release phase
        release_mask = pos_indices >= decay_end
        if np.any(release_mask):
            release_pos = pos_indices[release_mask] - decay_end
            envelope[release_mask] = self._sustain_level * np.exp(-5 * release_pos / self._release_len)

        # Generate waveform
        waveform, self._phase = _generate_waveform(
            self._freq, n, self._phase, self._waveform, self._harmonics
        )

        # Apply envelope and amplitude
        audio = (waveform * envelope * self._amp).astype(np.float32)

        self._pos += n

        # Pad with zeros if needed
        out = np.zeros(frames, dtype=np.float32)
        out[:n] = audio
        return out, self._pos >= self._total_len


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
            instrument = rule.get("instrument", "piano")
            print(f"[audio_engine]   Port {port}: note={rule.get('sound_type')}, instrument={instrument}, boost={rule.get('frequency_boost')}")
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

        note = rule.get("sound_type", DEFAULT_NOTE)
        freq = _note_to_freq(note)
        boost = rule.get("frequency_boost", 1.0)
        instrument = rule.get("instrument", "piano")

        print(f"[rule hit] port={dst_port} note={note} ({freq:.1f} Hz) instrument={instrument} boost={boost}")
        self._new_tones.put(InstrumentTone(freq, instrument, boost))

    def _callback(self, outdata, frames, time_info, status):
        if self._muted:
            outdata[:] = 0
            return

        while not self._new_tones.empty():
            self._active_tones.append(self._new_tones.get_nowait())

        signal = (np.random.randn(frames) * NOISE_AMPLITUDE).astype(np.float32)

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
