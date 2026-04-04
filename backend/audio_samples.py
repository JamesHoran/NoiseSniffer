"""
Professional-grade musical instrument engine using physical modeling synthesis.

Implements realistic instrument sounds without external samples:
- Piano: Additive synthesis with stretched harmonics
- Guitar: Karplus-Strong algorithm (plucked string physics)
- Flute: Physical model with noise burst
- Trumpet: Lip-reed physical model
- Bells: FM synthesis with inharmonic partials
- Chiptune: Classic square wave
- Synth: Analog-style sawtooth
"""
import queue
import threading
from collections import deque
from typing import Literal

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100
BLOCK_SIZE = 512

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

InstrumentType = Literal["piano", "guitar", "flute", "trumpet", "bells", "chiptune", "synth"]

# Sample cache for generated tones
_samples: dict[str, dict[str, np.ndarray]] = {}
_sample_lock = threading.Lock()


def _generate_piano(freq: float, duration: float = 1.5) -> np.ndarray:
    """Physical model of piano using additive synthesis with stretched harmonics."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # Piano harmonics with inharmonicity (stretched partials)
    # Real pianos have harmonics slightly sharp due to string stiffness
    B = 0.0004  # Inharmonicity coefficient
    audio = np.zeros_like(t)

    # First 16 harmonics with realistic amplitudes and stretched frequencies
    harmonics = [
        (1, 1.0), (2, 0.65), (3, 0.45), (4, 0.35),
        (5, 0.25), (6, 0.20), (7, 0.15), (8, 0.12),
        (9, 0.10), (10, 0.08), (12, 0.06), (16, 0.04)
    ]

    for n, amp in harmonics:
        # Stretched frequency due to inharmonicity
        stretched_freq = freq * n * np.sqrt(1 + B * n**2)
        audio += amp * np.sin(2 * np.pi * stretched_freq * t)

    # Normalize
    audio = audio / np.max(np.abs(audio))

    # Piano envelope (percussive attack, exponential decay)
    attack = int(0.005 * SAMPLE_RATE)
    decay_start = attack
    decay_len = len(t) - attack

    envelope = np.ones_like(t)
    envelope[:attack] = np.linspace(0, 1, attack)

    # Double exponential decay (fast initial, slow later)
    decay_fast = np.exp(-15 * np.linspace(0, 1, decay_len))
    decay_slow = np.exp(-2 * np.linspace(0, 1, decay_len))
    envelope[attack:] = 0.6 * decay_fast + 0.4 * decay_slow

    return (audio * envelope).astype(np.float32)


def _generate_guitar(freq: float, duration: float = 2.0) -> np.ndarray:
    """Physical model of guitar using Karplus-Strong algorithm."""
    # Karplus-Strong: delay line with averaging filter
    delay = int(SAMPLE_RATE / freq)
    total_len = int(SAMPLE_RATE * duration)

    # Initialize with noise (pluck excitation)
    buffer = np.random.uniform(-0.5, 0.5, delay + total_len).astype(np.float32)

    # Apply Karplus-Strong algorithm
    for i in range(delay, len(buffer)):
        # Averaging filter (simulates energy loss)
        buffer[i] = 0.5 * (buffer[i - delay] + buffer[i - delay - 1])

    # Extract the output
    output = buffer[delay:delay + total_len]

    # Apply envelope
    t = np.linspace(0, duration, total_len, False)
    envelope = np.exp(-3 * t)  # Pluck decay
    output *= envelope

    return output.astype(np.float32)


def _generate_flute(freq: float, duration: float = 1.0) -> np.ndarray:
    """Physical model of flute (air column with noise burst excitation)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # Flute has mostly odd harmonics
    audio = np.zeros_like(t)

    # Fundamental with even harmonics weaker
    harmonics = [(1, 0.8), (2, 0.05), (3, 0.35), (4, 0.02),
                 (5, 0.15), (6, 0.01), (7, 0.08)]

    for n, amp in harmonics:
        audio += amp * np.sin(2 * np.pi * freq * n * t)

    # Add breath noise (especially during attack)
    noise = np.random.normal(0, 0.1, len(t)).astype(np.float32)
    noise_envelope = np.exp(-20 * t)  # Quick decay
    audio += noise * noise_envelope

    # Vibrato (characteristic of flute)
    vibrato = 1.0 + 0.003 * np.sin(2 * np.pi * 5 * t)
    audio = audio * vibrato

    # Normalize and envelope
    audio = audio / np.max(np.abs(audio))
    attack = int(0.05 * SAMPLE_RATE)
    envelope = np.ones_like(t)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-int(0.1 * SAMPLE_RATE):] *= np.linspace(1, 0, int(0.1 * SAMPLE_RATE))

    return (audio * envelope).astype(np.float32)


def _generate_trumpet(freq: float, duration: float = 0.8) -> np.ndarray:
    """Physical model of trumpet (lip-reed instrument)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # Trumpet has rich harmonics (odd and even)
    audio = np.zeros_like(t)

    # Spectral envelope (bright, then mellows)
    harmonics = [(1, 0.5), (2, 0.6), (3, 0.5), (4, 0.4),
                 (5, 0.35), (6, 0.3), (7, 0.25), (8, 0.2),
                 (9, 0.15), (10, 0.1), (12, 0.08)]

    for n, amp in harmonics:
        audio += amp * np.sin(2 * np.pi * freq * n * t)

    # Add slight brightness (higher harmonics)
    brightness = 0.1 * np.sign(np.sin(2 * np.pi * freq * 3 * t))
    audio += brightness

    # Normalize
    audio = audio / np.max(np.abs(audio))

    # Trumpet envelope
    attack = int(0.03 * SAMPLE_RATE)
    envelope = np.ones_like(t)
    envelope[:attack] = np.linspace(0, 1, attack)

    # Sustain and release
    sustain_end = int(0.7 * SAMPLE_RATE)
    envelope[sustain_end:] *= np.linspace(1, 0, len(t) - sustain_end)

    return (audio * envelope).astype(np.float32)


def _generate_bells(freq: float, duration: float = 2.5) -> np.ndarray:
    """FM synthesis model for bells with inharmonic partials."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # FM synthesis for metallic sound
    carrier = freq
    modulator = freq * 1.4  # Inharmonic ratio
    index = 4.0  # Modulation index

    audio = 0.5 * np.sin(2 * np.pi * carrier * t +
                        index * np.sin(2 * np.pi * modulator * t))

    # Add inharmonic partials for bell-like quality
    partials = [
        (freq * 2.0, 0.3),
        (freq * 3.0, 0.2),
        (freq * 4.2, 0.15),  # Slightly sharp
        (freq * 5.4, 0.1),
    ]

    for p_freq, amp in partials:
        audio += amp * np.sin(2 * np.pi * p_freq * t)

    # Normalize
    audio = audio / np.max(np.abs(audio))

    # Long exponential decay
    envelope = np.exp(-1.5 * t)

    return (audio * envelope).astype(np.float32)


def _generate_chiptune(freq: float, duration: float = 0.3) -> np.ndarray:
    """Classic square wave (NES/8-bit style)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # Pure square wave
    audio = np.sign(np.sin(2 * np.pi * freq * t)) * 0.3

    # Quick envelope (characteristic of 8-bit sounds)
    envelope = np.ones_like(t)
    attack = int(0.001 * SAMPLE_RATE)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-int(0.05 * SAMPLE_RATE):] *= np.linspace(1, 0, int(0.05 * SAMPLE_RATE))

    return (audio * envelope).astype(np.float32)


def _generate_synth(freq: float, duration: float = 0.5) -> np.ndarray:
    """Analog-style sawtooth wave."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # Sawtooth wave (all harmonics at 1/n amplitude)
    n = np.arange(len(t))
    phase = 2 * np.pi * freq / SAMPLE_RATE * n
    phase = phase % (2 * np.pi)
    audio = (phase / np.pi - 1) * 0.25

    # Lowpass filter (analog synth character)
    # Simple moving average
    kernel_size = 8
    kernel = np.ones(kernel_size) / kernel_size
    audio = np.convolve(audio, kernel, mode='same')

    # Envelope
    attack = int(0.01 * SAMPLE_RATE)
    decay_start = int(0.2 * SAMPLE_RATE)
    envelope = np.ones_like(t)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[decay_start:] *= np.linspace(1, 0, len(t) - decay_start)

    return (audio * envelope).astype(np.float32)


def _load_and_pitch_shift(instrument: str, target_note: str) -> np.ndarray:
    """Generate instrument tone for target note."""
    freq = NOTES.get(target_note, NOTES[DEFAULT_NOTE])

    # Check cache
    if instrument in _samples and target_note in _samples[instrument]:
        return _samples[instrument][target_note]

    # Generate using physical model
    generators = {
        "piano": _generate_piano,
        "guitar": _generate_guitar,
        "flute": _generate_flute,
        "trumpet": _generate_trumpet,
        "bells": _generate_bells,
        "chiptune": _generate_chiptune,
        "synth": _generate_synth,
    }

    generator = generators.get(instrument, _generate_piano)
    audio = generator(freq)

    # Cache it
    if instrument not in _samples:
        _samples[instrument] = {}
    _samples[instrument][target_note] = audio

    return audio


def _compute_spectrum(samples: np.ndarray) -> list[float]:
    magnitude = np.abs(np.fft.rfft(samples * _HANN)) / FFT_SIZE
    db = 20 * np.log10(magnitude + 1e-10)
    normalised = np.clip((db - DB_MIN) / (DB_MAX - DB_MIN), 0.0, 1.0)
    return normalised[:NUM_BINS].tolist()


class InstrumentTone:
    """A playing instrument note with position tracking."""

    def __init__(self, note: str, instrument: str = "piano", boost: float = 1.0):
        self._samples = _load_and_pitch_shift(instrument, note) * boost
        self._pos = 0
        self._length = len(self._samples)

    def render(self, frames: int) -> tuple[np.ndarray, bool]:
        """Render up to `frames` samples of the instrument tone."""
        if self._pos >= self._length:
            return np.zeros(frames, dtype=np.float32), True

        n = min(frames, self._length - self._pos)
        audio = self._samples[self._pos:self._pos + n]

        # Fade out to avoid clicks
        fade_len = min(512, self._length - self._pos)
        if n >= fade_len:
            fade = np.linspace(1, 0, fade_len)
            audio[-fade_len:] *= fade

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
            instrument = rule.get('instrument', 'piano')
            note = rule.get('sound_type', DEFAULT_NOTE)
            boost = rule.get('frequency_boost', 1.0)
            print(f"[audio_engine]   Port {port}: {instrument} note={note} boost={boost}")
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
        boost = rule.get("frequency_boost", 1.0)
        instrument = rule.get("instrument", "piano")

        print(f"[rule hit] port={dst_port} {instrument} note={note} boost={boost}")
        self._new_tones.put(InstrumentTone(note, instrument, boost))

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
