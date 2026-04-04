"""
Piano-like synthesizer using additive synthesis.
Creates piano-like tones by layering multiple harmonics with piano-style envelopes.
"""
import numpy as np

SAMPLE_RATE = 44100

# Piano-like harmonic ratios and amplitudes
# Real pianos have complex harmonic series - these approximate the sound
PIANO_HARMONICS = [
    (1.0, 1.0),    # Fundamental
    (2.0, 0.6),    # 2nd harmonic (octave)
    (3.0, 0.3),    # 3rd harmonic (fifth)
    (4.0, 0.2),    # 4th harmonic (double octave)
    (5.0, 0.1),    # 5th harmonic
    (6.0, 0.05),   # 6th harmonic
    (7.0, 0.03),   # 7th harmonic
    (8.0, 0.02),   # 8th harmonic
]


class PianoTone:
    """
    Piano-like tone with additive synthesis and realistic envelope.

    Piano envelope has:
    - Fast attack (~5ms)
    - Initial decay (~50ms) - the percussive "knock"
    - Sustain (~0.3s) - the ringing sound
    - Release (~0.5s) - gradual fade out
    """
    ATTACK_S = 0.005   # 5 ms - very fast for piano
    DECAY_S = 0.05     # 50 ms - initial percussive decay
    SUSTAIN_LEVEL = 0.3  # 30% of initial volume
    RELEASE_S = 0.5    # 500 ms - final fade out
    TOTAL_S = ATTACK_S + DECAY_S + RELEASE_S

    def __init__(self, freq_hz: float, boost: float = 1.0):
        self._freq = freq_hz
        self._amp = 0.4 * boost  # Match original TONE_AMPLITUDE
        self._phase = 0.0

        # Calculate sample counts for each envelope stage
        self._attack_len = int(SAMPLE_RATE * self.ATTACK_S)
        self._decay_len = int(SAMPLE_RATE * self.DECAY_S)
        self._release_len = int(SAMPLE_RATE * self.RELEASE_S)
        self._total_len = self._attack_len + self._decay_len + self._release_len

        self._pos = 0

    def render(self, frames: int) -> tuple[np.ndarray, bool]:
        """Render up to `frames` samples of the piano tone."""
        n = min(frames, self._total_len - self._pos)
        if n <= 0:
            return np.zeros(frames, dtype=np.float32), True

        # Generate phase indices
        pos_indices = self._pos + np.arange(n)

        # Generate envelope
        envelope = np.zeros(n, dtype=np.float32)

        # Attack phase (linear rise to 1.0)
        attack_mask = pos_indices < self._attack_len
        envelope[attack_mask] = pos_indices[attack_mask] / self._attack_len

        # Decay phase (exponential decay to sustain level)
        decay_end = self._attack_len + self._decay_len
        decay_mask = (pos_indices >= self._attack_len) & (pos_indices < decay_end)
        if np.any(decay_mask):
            decay_pos = pos_indices[decay_mask] - self._attack_len
            # Exponential decay: sustain + (1-sustain) * exp(-t/tau)
            envelope[decay_mask] = self.SUSTAIN_LEVEL + (1 - self.SUSTAIN_LEVEL) * np.exp(-5 * decay_pos / self._decay_len)

        # Release phase (exponential decay to zero)
        release_mask = pos_indices >= decay_end
        if np.any(release_mask):
            release_pos = pos_indices[release_mask] - decay_end
            envelope[release_mask] = self.SUSTAIN_LEVEL * np.exp(-5 * release_pos / self._release_len)

        # Generate piano-like waveform using additive synthesis
        waveform = np.zeros(n, dtype=np.float32)
        phase_step = 2 * np.pi * self._freq / SAMPLE_RATE

        for harmonic_ratio, harmonic_amp in PIANO_HARMONICS:
            # Each harmonic has its own phase
            harmonic_phase = self._phase * harmonic_ratio
            phases = harmonic_phase + np.arange(n) * phase_step * harmonic_ratio
            waveform += np.sin(phases) * harmonic_amp

        # Normalize and apply envelope
        waveform = waveform / len(PIANO_HARMONICS) * self._amp * envelope
        waveform = waveform.astype(np.float32)

        # Update phase for next render (keep fundamental phase)
        self._phase = float((self._phase + np.arange(n)[-1] * phase_step) % (2 * np.pi)) if n > 0 else self._phase
        self._pos += n

        # Pad with zeros if needed
        out = np.zeros(frames, dtype=np.float32)
        out[:n] = waveform

        return out, self._pos >= self._total_len


def test_piano_tone():
    """Generate a test tone to verify piano synthesis."""
    import soundfile as sf

    tone = PianoTone(440.0, boost=1.0)  # A4

    # Generate 2 seconds of audio
    duration = 2.0
    total_frames = int(SAMPLE_RATE * duration)
    audio = np.zeros(total_frames, dtype=np.float32)

    pos = 0
    while pos < total_frames:
        frames = min(512, total_frames - pos)
        samples, done = tone.render(frames)
        audio[pos:pos + frames] = samples
        pos += frames
        if done and pos < total_frames:
            # Start a new note for demonstration
            tone = PianoTone(523.25, boost=1.0)  # C5

    # Normalize
    audio = np.clip(audio, -1.0, 1.0)

    # Save to file
    sf.write("piano_test.wav", audio, SAMPLE_RATE)
    print("Saved piano_test.wav")


if __name__ == "__main__":
    test_piano_tone()
