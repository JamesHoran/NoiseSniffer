"""
Sample-based musical instrument engine with pitch shifting.

Uses librosa to load instrument samples and pitch shift them to different notes.
Supports real instrument samples (WAV/MP3) for authentic sound.
"""
import queue
import threading
from collections import deque
from pathlib import Path
from typing import Literal

import numpy as np
import sounddevice as sd
import librosa

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

# Supported instrument types
InstrumentType = Literal["piano", "guitar", "flute", "trumpet", "bells", "chiptune", "synth"]

# Sample cache: _samples[instrument][note] = np.ndarray
_samples: dict[str, dict[str, np.ndarray]] = {}
_sample_lock = threading.Lock()

# Base note for each instrument (the sample we have)
_BASE_NOTES = {
    "piano": "C4",
    "guitar": "E3",
    "flute": "A4",
    "trumpet": "B3",
    "bells": "C5",
    "chiptune": "A4",
    "synth": "A4",
}


def _get_sample_path(instrument: str) -> Path | None:
    """Find a sample file for the given instrument."""
    # Try multiple locations
    paths = [
        Path(f"backend/samples/{instrument}.wav"),
        Path(f"backend/samples/{instrument}.mp3"),
        Path(f"samples/{instrument}.wav"),
        Path(f"samples/{instrument}.mp3"),
    ]
    for p in paths:
        if p.exists():
            return p
    return None


def _load_and_pitch_shift(instrument: str, target_note: str) -> np.ndarray:
    """Load instrument sample and pitch shift to target note."""
    # Get base note for this instrument
    base_note = _BASE_NOTES.get(instrument, DEFAULT_NOTE)
    base_freq = NOTES[base_note]
    target_freq = NOTES.get(target_note, NOTES[DEFAULT_NOTE])

    # Calculate semitone shift
    semitones = 12 * np.log2(target_freq / base_freq)

    # Check if we already have this sample cached
    if instrument in _samples and target_note in _samples[instrument]:
        return _samples[instrument][target_note]

    # Try to load a real sample
    sample_path = _get_sample_path(instrument)

    if sample_path:
        try:
            # Load audio file
            audio, sr = librosa.load(sample_path, sr=SAMPLE_RATE, mono=True)
            # Pitch shift
            if abs(semitones) > 0.01:
                audio = librosa.effects.pitch_shift(audio, sr=SAMPLE_RATE, n_steps=semitones)
            # Cache it
            if instrument not in _samples:
                _samples[instrument] = {}
            _samples[instrument][target_note] = audio
            return audio
        except Exception as e:
            print(f"[audio] Error loading {sample_path}: {e}")

    # Fallback: generate synthetic tone
    return _generate_synthetic_tone(instrument, target_note)


def _generate_synthetic_tone(instrument: str, note: str) -> np.ndarray:
    """Generate a synthetic tone as fallback when no sample is available."""
    freq = NOTES.get(note, NOTES[DEFAULT_NOTE])
    duration = 1.0  # seconds
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)

    # Different waveforms for different instruments
    if instrument == "piano":
        # Sine with harmonics
        audio = 0.6 * np.sin(2 * np.pi * freq * t)
        audio += 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        audio += 0.15 * np.sin(2 * np.pi * freq * 3 * t)
    elif instrument == "guitar":
        # Triangle-like
        audio = 0.5 * np.sign(np.sin(2 * np.pi * freq * t))
        audio += 0.3 * np.sign(np.sin(2 * np.pi * freq * 2 * t))
    elif instrument in ["trumpet", "synth"]:
        # Sawtooth-like
        n = np.arange(len(t))
        audio = 0.3 * np.sign(2 * (n * freq / SAMPLE_RATE - np.floor(0.5 + n * freq / SAMPLE_RATE)))
    elif instrument == "bells":
        # Sine with inharmonic partials
        audio = 0.5 * np.sin(2 * np.pi * freq * t)
        audio += 0.3 * np.sin(2 * np.pi * freq * 2.3 * t)
        audio += 0.2 * np.sin(2 * np.pi * freq * 5.4 * t)
    elif instrument == "chiptune":
        # Square wave
        audio = 0.3 * np.sign(np.sin(2 * np.pi * freq * t))
    else:
        audio = 0.5 * np.sin(2 * np.pi * freq * t)

    # Apply envelope (ADSR)
    envelope = np.ones_like(t)
    attack = int(0.01 * SAMPLE_RATE)
    decay = int(0.1 * SAMPLE_RATE)
    release = int(0.3 * SAMPLE_RATE)

    if len(t) > attack + decay + release:
        envelope[:attack] = np.linspace(0, 1, attack)
        envelope[attack:attack+decay] = np.linspace(1, 0.7, decay)
        envelope[-release:] = np.linspace(0.7, 0, release)

    audio = audio * envelope
    return audio.astype(np.float32)


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
