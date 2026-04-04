import queue
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from collections import deque
from scipy.signal import resample as scipy_resample

SAMPLE_RATE = 44100
BLOCK_SIZE  = 512

NOISE_AMPLITUDE = 0.08   # base white noise level
TONE_AMPLITUDE  = 0.4    # base sine burst amplitude

FFT_SIZE          = 2048
NUM_BINS          = 1024
SPECTRUM_INTERVAL = SAMPLE_RATE // 30
DB_MIN, DB_MAX    = -60.0, 0.0

_HANN = np.hanning(FFT_SIZE)

# Musical note → frequency (Hz), including sharps
NOTES: dict[str, float] = {
    "C3":  130.81, "C#3": 138.59, "D3":  146.83, "D#3": 155.56,
    "E3":  164.81, "F3":  174.61, "F#3": 185.00, "G3":  196.00,
    "G#3": 207.65, "A3":  220.00, "A#3": 233.08, "B3":  246.94,
    "C4":  261.63, "C#4": 277.18, "D4":  293.66, "D#4": 311.13,
    "E4":  329.63, "F4":  349.23, "F#4": 369.99, "G4":  392.00,
    "G#4": 415.30, "A4":  440.00, "A#4": 466.16, "B4":  493.88,
    "C5":  523.25, "C#5": 554.37, "D5":  587.33, "D#5": 622.25,
    "E5":  659.25, "F5":  698.46, "F#5": 739.99, "G5":  783.99,
    "G#5": 830.61, "A5":  880.00, "A#5": 932.33, "B5":  987.77,
}
DEFAULT_NOTE = "A4"

SOUNDS_DIR = Path(__file__).parent / "sounds"


def _note_to_freq(note: str) -> float:
    return NOTES.get(note, NOTES[DEFAULT_NOTE])


def _note_to_filename(note: str) -> str:
    """Convert 'C#4' → 'cs4', 'A#3' → 'as3', 'C3' → 'c3', etc."""
    return note.replace("#", "s").lower()


def _load_piano_samples() -> dict[str, np.ndarray]:
    """Pre-load all OGG piano samples from SOUNDS_DIR into memory."""
    samples: dict[str, np.ndarray] = {}
    for ogg_file in SOUNDS_DIR.glob("*.ogg"):
        key = ogg_file.stem  # e.g. "cs4", "a4", "b5"
        try:
            data, sr = sf.read(str(ogg_file), dtype="float32")
            if data.ndim > 1:
                data = data.mean(axis=1)  # mix stereo → mono
            if sr != SAMPLE_RATE:
                target_len = int(len(data) * SAMPLE_RATE / sr)
                data = scipy_resample(data, target_len).astype(np.float32)
            samples[key] = data
        except Exception as e:
            print(f"[audio] Failed to load {ogg_file}: {e}")
    print(f"[audio] Loaded {len(samples)} piano sample(s)")
    return samples


_PIANO_SAMPLES: dict[str, np.ndarray] = _load_piano_samples()


def _compute_spectrum(samples: np.ndarray) -> list[float]:
    magnitude = np.abs(np.fft.rfft(samples * _HANN)) / FFT_SIZE
    db = 20 * np.log10(magnitude + 1e-10)
    normalised = np.clip((db - DB_MIN) / (DB_MAX - DB_MIN), 0.0, 1.0)
    return normalised[:NUM_BINS].tolist()


class _Tone:
    """0.5s sine wave burst with a short attack and linear decay."""
    ATTACK_S = 0.02   # 20 ms
    DECAY_S  = 0.48   # 480 ms  →  total 0.5 s

    def __init__(self, freq_hz: float, boost: float = 1.0):
        self._freq   = freq_hz
        self._amp    = TONE_AMPLITUDE * boost
        self._attack = int(SAMPLE_RATE * self.ATTACK_S)
        self._decay  = int(SAMPLE_RATE * self.DECAY_S)
        self._total  = self._attack + self._decay
        self._pos    = 0
        self._phase  = 0.0

    def render(self, frames: int) -> tuple[np.ndarray, bool]:
        n = min(frames, self._total - self._pos)

        phase_step = 2 * np.pi * self._freq / SAMPLE_RATE
        phases = self._phase + np.arange(n) * phase_step
        sine   = np.sin(phases) * self._amp

        pos_idx = self._pos + np.arange(n)
        env = np.where(
            pos_idx < self._attack,
            pos_idx / self._attack,
            1.0 - (pos_idx - self._attack) / self._decay,
        ).clip(0.0, 1.0)

        out = np.zeros(frames, dtype=np.float32)
        out[:n] = (sine * env).astype(np.float32)

        self._phase = float(phases[-1]) + phase_step if n > 0 else self._phase
        self._pos  += n
        return out, self._pos >= self._total


class _PianoTone:
    """Plays a pre-loaded piano OGG sample scaled by boost."""

    def __init__(self, samples: np.ndarray, boost: float = 1.0):
        self._samples = (samples * TONE_AMPLITUDE * boost).astype(np.float32)
        self._pos = 0

    def render(self, frames: int) -> tuple[np.ndarray, bool]:
        remaining = len(self._samples) - self._pos
        n = min(frames, remaining)
        out = np.zeros(frames, dtype=np.float32)
        if n > 0:
            out[:n] = self._samples[self._pos:self._pos + n]
        self._pos += n
        return out, self._pos >= len(self._samples)


class AudioEngine:
    def __init__(self):
        self._new_tones: queue.SimpleQueue[_Tone | _PianoTone] = queue.SimpleQueue()
        self._active_tones: list[_Tone | _PianoTone] = []
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
            print(f"[audio_engine]   Port {port}: sound={rule.get('sound')} note={rule.get('sound_type')}, boost={rule.get('frequency_boost')}, whitelist={rule.get('ip_whitelist')}")
        print(f"[rules] {len(rules)} rule(s) active — ports: {list(rules.keys())}")

    def on_packet(self, parsed: dict):
        dst_port = parsed.get("dst_port") or 0
        src_ip   = parsed.get("src_ip", "")
        rule     = self._rules.get(dst_port)

        if rule:
            whitelist = rule.get("ip_whitelist", [])
            if whitelist and src_ip not in whitelist:
                rule = None

        if not rule:
            return  # no rule = no tone, only white noise

        note  = rule.get("sound_type", DEFAULT_NOTE)
        boost = rule.get("frequency_boost", 1.0)
        sound = rule.get("sound", "synth")

        if sound == "piano":
            filename = _note_to_filename(note)
            sample_data = _PIANO_SAMPLES.get(filename)
            if sample_data is not None:
                print(f"[rule hit] port={dst_port} note={note} (piano) boost={boost}")
                self._new_tones.put(_PianoTone(sample_data, boost))
            else:
                print(f"[rule hit] port={dst_port} note={note} (piano) — sample not found, falling back to synth")
                freq = _note_to_freq(note)
                self._new_tones.put(_Tone(freq, boost))
        else:
            freq = _note_to_freq(note)
            print(f"[rule hit] port={dst_port} note={note} ({freq:.1f} Hz) boost={boost}")
            self._new_tones.put(_Tone(freq, boost))

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
