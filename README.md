# NoiseSniffer

**Hear your network traffic in real-time.** An innovative security monitoring tool that converts network packets into sound—making threats like port scans and DDoS attacks immediately obvious to the ear.

> "What would your network sound like if it could play itself?"

By James Horan and Oliver Tasset

---

## Overview

NoiseSniffer is a network monitoring application that turns live traffic into audio. Instead of staring at scrolling log files, you hear your network's patterns as they happen. Each network port plays a different musical note—normal traffic becomes a familiar soundscape, and anything unusual stands out instantly.

### Why Audio Works

The human ear is naturally good at detecting patterns. We notice when a rhythm changes, when a new sound appears, or when something gets too loud. NoiseSniffer applies this to network security:

- **Normal traffic** sounds like a familiar melody
- **Port scanning** sounds like rapid-fire notes
- **DDoS attacks** create a "wall of sound"
- **Silence** means the network went down

You can monitor your network while focusing on other work—your ears will alert you when something changes.

### What Makes This Different

Traditional network monitoring tools require constant visual attention. You have to watch logs, interpret data, and often notice problems only after alarms trigger. NoiseSniffer provides immediate, intuitive awareness—you hear changes as they happen.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Network Interface                    │
│                           (Scapy sniffing)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      Python Backend                          │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   Scapy     │───▶│    Queue     │───▶│  Audio Engine │  │
│  │  (thread)   │    │  (async)     │    │   (realtime)  │  │
│  └─────────────┘    └──────┬───────┘    └───────┬───────┘  │
│                             │                    │           │
│                             ▼                    ▼           │
│                      ┌──────────────┐    ┌───────────────┐  │
│                      │   WebSocket  │    │  FFT Spectrum │  │
│                      │  Broadcast   │    │   Analysis    │  │
│                      └──────┬───────┘    └───────────────┘  │
└─────────────────────────────┼──────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Spectrum   │  │  Packet      │  │     Rules         │  │
│  │  Visualizer │  │  Stream      │  │   Management      │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.14, FastAPI, Uvicorn |
| **Packet Capture** | Scapy |
| **Audio** | sounddevice (OutputStream), soundfile (OGG decode), scipy (resampling) |
| **Signal Processing** | NumPy (FFT, sine generation) |
| **Frontend** | React 19, TypeScript, Tailwind CSS v4 |
| **Data Grid** | TanStack Table (virtualized, headless UI) |
| **Visualization** | uPlot (high-performance canvas charting) |
| **Package Managers** | pipenv (backend), pnpm (frontend) |

### Design Decisions

#### Why TanStack Table?
TanStack Table (`@tanstack/react-table`) was chosen for the live packet stream to prevent UI crashes under high-throughput conditions. The table implements a buffer-flush pattern where WebSocket messages accumulate in a ref (bypassing React re-renders) and flush to state periodically. This prevents the UI from freezing when receiving hundreds of packets per second.

#### Real-time Audio Architecture
The audio engine uses a lock-free queue and non-blocking callback to achieve zero-latency playback. Packet capture runs on a dedicated OS thread and hands data to the async event loop via `call_soon_threadsafe`, ensuring no packets are dropped while maintaining smooth audio output.

---

## How It Works

### 1. Packet Capture
Scapy runs on a background OS thread, listening on the configured network interface (`IFACE` env var). Packets are parsed and handed to the async event loop via `call_soon_threadsafe`.

### 2. Rule Engine
Each packet is matched against configured rules:
- **Port** — which port triggers the rule
- **IP Whitelist** — optional filtering by source/destination IP
- **Sound Type** — `synth` or `piano`
- **Note** — any chromatic note from C3 to B5 (36 notes total)
- **Frequency Boost** — amplitude multiplier (1.0 = neutral)

### 3. Audio Generation
Two tone types share the same interface:
- **Synth** — synthesized sine burst (10ms attack, 300ms decay)
- **Piano** — plays a pre-loaded OGG sample, scaled by frequency boost

All 36 piano samples (C3–B5) are decoded and resampled to 44.1kHz at startup. Base white noise runs constantly; tones are mixed on top via a real-time `sounddevice.OutputStream` callback.

**During high-volume attacks** (SYN flood, DDoS), the sheer number of packets pushes the sound into natural distortion—a clear audio indicator that something is wrong.

### 4. Spectrum Analysis
A 1024-bin FFT analyzes the audio output in real-time, normalized to -100...0 dB range. Frequency annotations are added for active tones.

### 5. WebSocket Broadcast
- Spectrum data sent 60×/second
- Packet events sent immediately
- Frontend reacts without polling

---

## Installation & Running

### Prerequisites
- Python 3.14+
- Node.js 18+
- pipenv
- pnpm

### Backend

```bash
cd backend
pipenv install
pipenv shell
uvicorn main:app --reload
```

Backend runs at `http://localhost:8000`

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Frontend runs at `http://localhost:3000`

### WebSocket Connection
`ws://localhost:8000/ws`

---

## Configuration

### Network Interface
Set via `backend/.env`:
```
IFACE=eth0
```

### Rules
Rules are stored in `backend/rules.json` and hot-reloaded on file changes.

Example rule:
```json
{
  "port": 443,
  "ip_whitelist": [],
  "sound": "piano",
  "sound_type": "C4",
  "frequency_boost": 1.5
}
```

---

## UI Features

### Tab 1: Spectrum
Real-time FFT spectrum visualization showing audio frequencies. Active packet tones appear as peaks on the spectrum, letting you see which ports are generating traffic.

### Tab 2: Packets
Live packet stream table similar to Wireshark, showing:
- Timestamp
- Source IP
- Destination IP
- Protocol
- Packet length

### Tab 3: Rules
Create and manage rules for port-based audio mapping:
- **Port number** (1-65535)
- **Sound type** (synth or piano)
- **Note selection** (all 36 chromatic notes C3–B5)
- **Frequency boost** (0-10×, controls volume)
- **IP whitelist** (optional comma-separated IPs, empty = all)

Presets included for common configurations.

---

## Use Cases

| Scenario | What You Hear |
|----------|---------------|
| **Normal traffic** | Familiar patterns—HTTPS humming, occasional SSH chirps, DNS rippling |
| **Port scanning** | Rapid-fire sequence across unfamiliar ports (staccato attack) |
| **DDoS attack** | Single note overwhelming everything else (wall of sound) |
| **New service** | A new voice joins the symphony (investigate or add rule) |
| **Silence** | Network went down (no traffic = no sound) |

---

## API Reference

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/rules` | GET | Get all rules |
| `/rules` | POST | Create/update rule |
| `/rules/{port}` | DELETE | Delete rule by port |
| `/mute` | POST | Mute/unmute audio |

### WebSocket Messages

#### Spectrum (60 Hz)
```typescript
{
  type: "spectrum",
  bins: number[],      // 1024 FFT bins, -100 to 0 dB
  annotations?: Array<{
    label: string,
    frequency: number
  }>
}
```

#### Packet (real-time)
```typescript
{
  type: "packet",
  timestamp: string,
  src_ip: string,
  dst_ip: string,
  protocol: string,
  length: number
}
```

---

## Project Structure

```
NoiseSniffer/
├── backend/
│   ├── main.py          # FastAPI app, WebSocket, REST endpoints
│   ├── audio.py         # AudioEngine, tone synthesis, FFT
│   ├── rules.py         # Rule CRUD, JSON persistence, file watcher
│   ├── sniffer.py       # Scapy packet parsing
│   ├── sounds/*.ogg     # Piano samples C3–B5
│   └── rules.json       # Persisted rules
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── SpectrumAnalyzer.tsx
│       │   ├── PacketStream.tsx
│       │   └── RulesTab.tsx
│       ├── hooks/
│       │   └── useWebSocket.ts
│       └── App.tsx
└── README.md
```

---

## License

MIT
