import queue
import time
from pathlib import Path

import numpy as np
import scipy.signal
import sounddevice as sd
from collections import deque
from scipy.io import wavfile

SAMPLE_RATE = 44100
BLOCK_SIZE = 512

NOISE_AMPLITUDE = 0.08       # base white noise level
BURST_AMPLITUDE = 0.2        # base amplitude for sound bursts
DISTORTION_THRESHOLD = 50    # packets/sec before distortion kicks in

FFT_SIZE = 2048
NUM_BINS = 1024
SPECTRUM_INTERVAL = SAMPLE_RATE // 30  # emit a new spectrum every ~33ms
DB_MIN, DB_MAX = -60.0, 0.0

_HANN = np.hanning(FFT_SIZE)

SOUNDS_DIR = Path(__file__).parent / "sounds"
SOUND_NAMES = ["fire", "synth", "rain", "wind"]

# Loaded sound buffers: sound_type -> float32 mono array normalised to [-1, 1]
_sound_buffers: dict[str, np.ndarray] = {}


def _load_sounds():
    """Load all WAV files from the sounds/ directory into memory."""
    for name in SOUND_NAMES:
        path = SOUNDS_DIR / f"{name}.wav"
        if not path.exists():
            print(f"[audio] {path.name} not found, skipping.")
            continue
        try:
            rate, data = wavfile.read(path)
            if data.ndim > 1:
                data = data.mean(axis=1)             # stereo → mono
            data = data.astype(np.float32)
            peak = np.abs(data).max()
            if peak > 0:
                data /= peak                          # normalise to [-1, 1]
            if rate != SAMPLE_RATE:
                n_samples = int(len(data) * SAMPLE_RATE / rate)
                data = scipy.signal.resample(data, n_samples).astype(np.float32)
            _sound_buffers[name] = data
            print(f"[audio] Loaded {path.name} ({len(data) / SAMPLE_RATE:.1f}s)")
        except Exception as e:
            print(f"[audio] Could not load {path.name}: {e}")


def _get_sound_frames(sound_type: str, buf_pos: int, n: int) -> tuple[np.ndarray, int]:
    """Return n frames from a looping sound buffer, starting at buf_pos."""
    if sound_type not in _sound_buffers:
        return np.random.randn(n).astype(np.float32), buf_pos

    buf = _sound_buffers[sound_type]
    buf_len = len(buf)
    out = np.zeros(n, dtype=np.float32)
    written = 0
    pos = buf_pos % buf_len

    while written < n:
        take = min(n - written, buf_len - pos)
        out[written:written + take] = buf[pos:pos + take]
        written += take
        pos = (pos + take) % buf_len

    return out, pos


def _design_bandpass(center_hz: float) -> np.ndarray:
    """
    4th-order Butterworth bandpass SOS filter centred at center_hz.
    Bandwidth is ±1 octave (low = center/√2, high = center×√2).
    """
    nyq = SAMPLE_RATE / 2
    low = max(center_hz / 1.4142, 30.0)
    high = min(center_hz * 1.4142, nyq * 0.98)
    if low >= high:
        high = min(low * 1.5, nyq * 0.98)
    return scipy.signal.butter(4, [low / nyq, high / nyq], btype="band", output="sos")


def _compute_spectrum(samples: np.ndarray) -> list[float]:
    """FFT → dB → normalised [0,1]."""
    magnitude = np.abs(np.fft.rfft(samples * _HANN)) / FFT_SIZE
    db = 20 * np.log10(magnitude + 1e-10)
    normalised = np.clip((db - DB_MIN) / (DB_MAX - DB_MIN), 0.0, 1.0)
    return normalised[:NUM_BINS].tolist()


def _freq_for_packet(parsed: dict) -> float:
    """Map a parsed packet to a frequency (Hz) based on protocol/port."""
    protocol = parsed.get("protocol", "")
    dst_port = parsed.get("dst_port") or 0
    if protocol == "TCP":
        return 600 + (dst_port % 2400)   # 600–3000 Hz
    elif protocol == "UDP":
        return 200 + (dst_port % 400)    # 200–600 Hz
    elif protocol == "ICMP":
        return 120
    return 300


class _SoundBurst:
    """
    A short burst of a sound type (WAV or white noise) shaped by a bandpass
    filter and an attack/decay envelope. Replaces the old sine-wave _Tone.

    The bandpass filter acts like an EQ band — only frequencies near center_hz
    pass through, giving each packet a distinct tonal character based on its
    port/protocol and the rule's sound_type.
    """
    ATTACK_S = 0.02   # 20 ms
    DECAY_S  = 0.30   # 300 ms

    def __init__(self, sound_type: str, center_hz: float, boost: float = 1.0):
        self._sound_type = sound_type
        self._boost = boost
        self._attack = int(SAMPLE_RATE * self.ATTACK_S)
        self._decay  = int(SAMPLE_RATE * self.DECAY_S)
        self._total  = self._attack + self._decay
        self._pos    = 0

        # Start at a random offset in the buffer so successive bursts vary
        if sound_type in _sound_buffers:
            self._buf_pos = int(np.random.randint(0, len(_sound_buffers[sound_type])))
        else:
            self._buf_pos = 0

        # Design bandpass filter and zero its initial conditions
        sos = _design_bandpass(center_hz)
        self._sos = sos
        self._zi  = scipy.signal.sosfilt_zi(sos) * 0.0  # shape: (n_sections, 2)

    def render(self, frames: int) -> tuple[np.ndarray, bool]:
        n = min(frames, self._total - self._pos)

        # Get source audio (WAV loop or white noise fallback)
        source, self._buf_pos = _get_sound_frames(self._sound_type, self._buf_pos, n)

        # Apply bandpass filter — stateful so it's continuous across render() calls
        filtered, self._zi = scipy.signal.sosfilt(self._sos, source, zi=self._zi)
        filtered = filtered.astype(np.float32)

        # Linear attack / linear decay envelope
        pos_idx = self._pos + np.arange(n)
        env = np.where(
            pos_idx < self._attack,
            pos_idx / self._attack,
            1.0 - (pos_idx - self._attack) / self._decay,
        ).clip(0.0, 1.0).astype(np.float32)

        out = np.zeros(frames, dtype=np.float32)
        out[:n] = filtered * env * BURST_AMPLITUDE * self._boost

        self._pos += n
        return out, self._pos >= self._total


class AudioEngine:
    def __init__(self):
        # SimpleQueue is lock-free and safe to write from any thread.
        self._new_bursts: queue.SimpleQueue[_SoundBurst] = queue.SimpleQueue()
        self._new_timestamps: queue.SimpleQueue[float] = queue.SimpleQueue()
        # Only touched inside the audio callback thread.
        self._active_bursts: list[_SoundBurst] = []
        self._packet_times: deque[float] = deque()
        self._stream: sd.OutputStream | None = None
        # Port-keyed rules — replaced atomically (GIL-safe).
        self._rules: dict[int, dict] = {}
        self._muted: bool = False
        # Spectrum state
        self._sample_buffer: deque[float] = deque(maxlen=FFT_SIZE)
        self._samples_since_spectrum: int = 0
        self.latest_spectrum: list[float] | None = None

    def start(self):
        _load_sounds()
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
        """Replace active rules. Called by the watchdog or POST /rules."""
        self._rules = rules

    def on_packet(self, parsed: dict):
        """Feed a parsed packet into the engine. Safe to call from any thread."""
        dst_port = parsed.get("dst_port") or 0
        src_ip   = parsed.get("src_ip", "")
        rule     = self._rules.get(dst_port)

        # If the rule has an IP whitelist, only apply it when src_ip is in the list
        if rule:
            whitelist = rule.get("ip_whitelist", [])
            if whitelist and src_ip not in whitelist:
                rule = None

        sound_type = rule.get("sound_type", "white_noise") if rule else "white_noise"
        boost      = rule.get("frequency_boost", 1.0) if rule else 1.0
        center_hz  = rule.get("frequency_hz") or _freq_for_packet(parsed)

        self._new_bursts.put(_SoundBurst(sound_type, center_hz, boost))
        self._new_timestamps.put(time.monotonic())

    def _callback(self, outdata, frames, time_info, status):
        """Called by sounddevice on its own audio thread to fill each output buffer."""
        if self._muted:
            outdata[:] = 0
            return

        # Drain incoming bursts
        while not self._new_bursts.empty():
            self._active_bursts.append(self._new_bursts.get_nowait())

        # Update rolling 1-second packet rate window
        now = time.monotonic()
        while not self._new_timestamps.empty():
            self._packet_times.append(self._new_timestamps.get_nowait())
        while self._packet_times and now - self._packet_times[0] > 1.0:
            self._packet_times.popleft()

        # Base white noise layer
        signal = (np.random.randn(frames) * NOISE_AMPLITUDE).astype(np.float32)

        # Mix in active bursts, removing finished ones
        dead = []
        for i, burst in enumerate(self._active_bursts):
            samples, done = burst.render(frames)
            signal += samples
            if done:
                dead.append(i)
        for i in reversed(dead):
            self._active_bursts.pop(i)

        # Waveshaping distortion on packet rate spike
        rate = len(self._packet_times)
        if rate > DISTORTION_THRESHOLD:
            excess = min((rate - DISTORTION_THRESHOLD) / DISTORTION_THRESHOLD, 1.0)
            gain = 1.0 + excess * 4.0
            signal = np.tanh(signal * gain)

        outdata[:, 0] = np.clip(signal, -1.0, 1.0)

        # Accumulate samples for spectrum
        self._sample_buffer.extend(outdata[:, 0].tolist())
        self._samples_since_spectrum += frames
        if self._samples_since_spectrum >= SPECTRUM_INTERVAL and len(self._sample_buffer) == FFT_SIZE:
            self.latest_spectrum = _compute_spectrum(np.array(self._sample_buffer, dtype=np.float32))
            self._samples_since_spectrum = 0


engine = AudioEngine()
