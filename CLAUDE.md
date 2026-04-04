# NoiseSniffer — Claude Context

Network packet sniffer that turns live traffic into audio. Each rule maps a port → a sound and note, so the network literally sounds like itself.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.14, FastAPI, uvicorn |
| Packet capture | Scapy |
| Audio | sounddevice (OutputStream), soundfile (OGG decode), scipy (resampling) |
| Signal | NumPy (FFT, sine generation) |
| Frontend | React 19, TypeScript, Tailwind CSS |
| Package managers | pipenv (backend), pnpm (frontend) |

## Running

```bash
# Terminal 1 — backend (from repo root)
cd backend && pipenv install && pipenv shell
uvicorn main:app --reload

# Terminal 2 — frontend
cd frontend && pnpm install && pnpm dev
```

Backend: `http://localhost:8000`  
Frontend: `http://localhost:3000`  
WebSocket: `ws://localhost:8000/ws`

Network interface is set via `IFACE` in `backend/.env`.

## Architecture

```
Scapy thread  ──→  asyncio.Queue  ──→  _broadcast_loop()  ──→  WebSocket clients
                                   └──→  audio_engine.on_packet()
```

- Scapy runs on a blocking OS thread; packets are handed to the async event loop via `call_soon_threadsafe`.
- `audio_engine` runs a `sounddevice.OutputStream` with a real-time callback — never block inside it.
- Rules are persisted to `backend/rules.json`. Watchdog monitors the file for external edits and hot-reloads them.

## Key files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, WebSocket, REST endpoints, startup wiring |
| `backend/audio.py` | AudioEngine, tone synthesis, OGG piano playback, FFT spectrum |
| `backend/rules.py` | Rule CRUD, JSON persistence, watchdog file watcher |
| `backend/sniffer.py` | Scapy packet parsing → normalised dict |
| `backend/sounds/*.ogg` | Piano samples C3–B5 (36 chromatic notes, named e.g. `cs4.ogg` for C#4) |
| `frontend/src/components/RulesTab.tsx` | Rule creation/management UI |
| `frontend/src/components/SpectrumAnalyzer.tsx` | FFT spectrum visualisation |
| `frontend/src/hooks/useWebSocket.ts` | WebSocket connection with auto-reconnect |
| `schema.md` | Canonical WebSocket and REST API schemas |

## Audio engine

Two tone types share the same `render(frames) -> (ndarray, done)` interface:

- `_Tone` — synthesized sine burst (20 ms attack, 480 ms decay) at the note's frequency
- `_PianoTone` — plays a pre-loaded OGG sample scaled by `frequency_boost`

All OGG files are decoded and resampled to 44100 Hz at startup into `_PIANO_SAMPLES` (keyed by filename stem, e.g. `"cs4"`). Note names use `#` notation (`"C#4"`); `_note_to_filename` converts to the file key.

Base white noise (`NOISE_AMPLITUDE = 0.08`) runs constantly. Tones are mixed on top.

## Rule schema

```json
{
  "port": 443,
  "ip_whitelist": [],
  "sound": "piano",
  "sound_type": "C#4",
  "frequency_boost": 1.5
}
```

- `sound`: `"synth"` | `"piano"` (defaults to `"synth"` if absent)
- `sound_type`: any of the 36 chromatic notes C3–B5 including sharps (`"C#3"` … `"A#5"`)
- `frequency_boost`: amplitude multiplier, 1.0 = neutral

## Frontend note naming

Sharp notes use `#` (e.g. `"C#4"`), matching the backend `NOTES` dict and displayed in chromatic order in the Note dropdown.
