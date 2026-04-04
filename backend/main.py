import asyncio
import json
import os
import random
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from scapy.all import sniff, conf as scapy_conf
from sniffer import parse_packet

load_dotenv()
IFACE = os.environ["IFACE"]  # set in .env

app = FastAPI()

# The core problem: Scapy's sniff() is blocking — it runs a while True loop on its own OS thread.
# FastAPI/uvicorn is async — it runs everything on a single-threaded event loop. These two worlds can't
# call each other directly, so there's a bridge in between.

# Every currently connected frontend WebSocket client.
_clients: set[WebSocket] = set()
# Lock so the broadcast loop and the /ws endpoint don't mutate _clients at the same time.
_clients_lock = asyncio.Lock()

# Reference to the running event loop — captured at startup so the Scapy thread
# (which has no event loop of its own) can schedule work onto it safely.
_loop: asyncio.AbstractEventLoop | None = None

# Thread-safe bridge: Scapy thread puts packet JSON in here;
# the async broadcast loop pulls it out.
_queue: asyncio.Queue = asyncio.Queue()

# Spectrum analyzer state
BINS = 1024
_spectrum_lock = threading.Lock()
# Traffic counters per protocol/port - maps to frequency bins
_traffic_counters: dict[int, float] = defaultdict(float)
# Last seen protocols for annotations
_active_protocols: dict[str, tuple[int, float]] = {}  # protocol -> (bin_index, amplitude)
# Timestamp of last spectrum update
_last_spectrum_time: float = time.time()

# Protocol to frequency bin mappings (spread across spectrum)
_PROTOCOL_BINS = {
    "HTTP": 50,
    "HTTPS": 80,
    "DNS": 150,
    "SSH": 220,
    "NTP": 350,
    "ARP": 500,
    "ICMP": 650,
    "TCP": 800,
    "UDP": 900,
}


def _get_protocol_from_packet(parsed: dict) -> str | None:
    """Extract protocol name from parsed packet for spectrum mapping."""
    protocol = parsed.get("protocol")
    dst_port = parsed.get("dst_port")

    # Map common ports to protocol names
    if dst_port:
        if dst_port == 80:
            return "HTTP"
        elif dst_port == 443:
            return "HTTPS"
        elif dst_port == 53:
            return "DNS"
        elif dst_port == 22:
            return "SSH"
        elif dst_port == 123:
            return "NTP"

    return protocol


def _on_packet(packet):
    """Called by Scapy on the sniffer thread for every captured packet."""
    parsed = parse_packet(packet)
    if parsed and _loop is not None:
        # call_soon_threadsafe is the only safe way to hand data from a
        # non-async thread to the asyncio event loop without blocking either side.
        _loop.call_soon_threadsafe(_queue.put_nowait, json.dumps(parsed))

        # Update spectrum data
        protocol = _get_protocol_from_packet(parsed)
        if protocol:
            bin_idx = _PROTOCOL_BINS.get(protocol)
            if bin_idx is not None:
                with _spectrum_lock:
                    # Add energy to this bin (decays over time)
                    _traffic_counters[bin_idx] += 0.3
                    # Track for annotations
                    _active_protocols[protocol] = (bin_idx, min(1.0, _traffic_counters[bin_idx]))


def _generate_spectrum_data() -> dict:
    """Generate spectrum data from current traffic state."""
    with _spectrum_lock:
        # Decay all counters
        for bin_idx in list(_traffic_counters.keys()):
            _traffic_counters[bin_idx] *= 0.95
            if _traffic_counters[bin_idx] < 0.01:
                del _traffic_counters[bin_idx]

        # Build bins array
        bins = [0.0] * BINS

        # Fill with noise floor
        noise_floor = 0.1 + random.random() * 0.05
        for i in range(BINS):
            bins[i] = noise_floor + random.random() * 0.02

        # Add traffic energy to bins
        for bin_idx, energy in _traffic_counters.items():
            if 0 <= bin_idx < BINS:
                # Spread energy across nearby bins (Gaussian-like)
                for offset in range(-10, 11):
                    idx = bin_idx + offset
                    if 0 <= idx < BINS:
                        spread = energy * (1.0 - abs(offset) / 11)
                        bins[idx] = min(1.0, bins[idx] + spread)

        # Build annotations from active protocols
        annotations = []
        current_time = time.time()
        for protocol, (bin_idx, amplitude) in list(_active_protocols.items()):
            if amplitude > 0.1 and current_time - _last_spectrum_time < 1.0:
                annotations.append({
                    "label": protocol,
                    "frequency": bin_idx
                })
            elif amplitude < 0.05:
                del _active_protocols[protocol]

        _last_spectrum_time = current_time

        return {
            "type": "spectrum",
            "bins": bins,
            "annotations": annotations if annotations else None
        }


def _start_sniffer():
    """Blocking Scapy capture loop — runs on a background OS thread."""
    scapy_conf.verb = 0  # suppress Scapy's console output
    sniff(iface=IFACE, filter="ip", prn=_on_packet, store=False)


@app.on_event("startup")
async def startup():
    global _loop
    # Grab the event loop now, while we're inside async context.
    _loop = asyncio.get_running_loop()

    # Run Scapy on a daemon thread so it doesn't block the event loop.
    # daemon=True means the thread is killed automatically when the process exits.
    t = threading.Thread(target=_start_sniffer, daemon=True)
    t.start()

    # Launch the broadcast loop as a background async task.
    asyncio.create_task(_broadcast_loop())

    # Launch the spectrum broadcast loop (~30fps)
    asyncio.create_task(_spectrum_broadcast_loop())


async def _broadcast_loop():
    """Drains the packet queue and sends each message to all connected clients."""
    while True:
        message = await _queue.get()  # waits until a packet arrives
        async with _clients_lock:
            dead = set()
            for ws in _clients:
                try:
                    await ws.send_text(message)
                except Exception:
                    # Client disconnected or errored mid-send — mark for removal.
                    dead.add(ws)
            for ws in dead:
                _clients.discard(ws)


async def _spectrum_broadcast_loop():
    """Generates and sends spectrum data at ~30fps."""
    while True:
        spectrum = _generate_spectrum_data()
        message = json.dumps(spectrum)

        async with _clients_lock:
            dead = set()
            for ws in _clients:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                _clients.discard(ws)

        await asyncio.sleep(1 / 30)  # ~30 fps


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Accepts a frontend connection and registers it to receive packet broadcasts."""
    await ws.accept()
    async with _clients_lock:
        _clients.add(ws)
    try:
        # Loop keeps the connection open. We don't expect messages from the client
        # at this stage, but receive_text() yields control back to the event loop
        # so the broadcast loop can still run.
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        # Always deregister, whether the client left cleanly or not.
        async with _clients_lock:
            _clients.discard(ws)
