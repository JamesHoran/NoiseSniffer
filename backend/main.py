import asyncio
import json
import os
import threading
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scapy.all import sniff, conf as scapy_conf
from sniffer import parse_packet
from audio_ambient import engine as audio_engine
from rules import save_rule, delete_rule, get_rules, start_watcher

load_dotenv()
IFACE = os.environ["IFACE"]  # set in .env

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def _on_packet(packet):
    """Called by Scapy on the sniffer thread for every captured packet."""
    parsed = parse_packet(packet)
    if parsed and _loop is not None:
        # call_soon_threadsafe is the only safe way to hand data from a
        # non-async thread to the asyncio event loop without blocking either side.
        _loop.call_soon_threadsafe(_queue.put_nowait, json.dumps(parsed))


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

    # Start the audio engine (opens the sounddevice output stream).
    audio_engine.start()

    # Load rules.json and watch for external changes.
    start_watcher(audio_engine.update_rules)

    # Launch the broadcast loop as a background async task.
    asyncio.create_task(_broadcast_loop())
    asyncio.create_task(_spectrum_loop())


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

        # Feed the packet into the audio engine.
        audio_engine.on_packet(json.loads(message))


class MuteRequest(BaseModel):
    muted: bool


@app.post("/mute")
async def set_mute(body: MuteRequest):
    audio_engine.set_muted(body.muted)
    return {"muted": body.muted}


class Rule(BaseModel):
    port: int
    ip_whitelist: list[str] = []
    sound_type: str = "rain"  # Ambient sound: rain, wind, fire, forest, drones, hospital_beep
    frequency_boost: float = 1.0  # Volume boost for the sound


@app.get("/rules")
async def list_rules():
    print(f"[http GET /rules] Returning rules")
    rules = list(get_rules().values())
    print(f"[http GET /rules] Returning {len(rules)} rule(s)")
    return rules


@app.post("/rules", status_code=201)
async def post_rule(rule: Rule):
    """Create or update a rule for a given port."""
    print(f"[http POST /rules] Received rule: {rule.model_dump()}")
    rule_dict = rule.model_dump()
    save_rule(rule_dict)
    print(f"[http POST /rules] Calling audio_engine.update_rules with current rules")
    audio_engine.update_rules(get_rules())
    print(f"[http POST /rules] Returning saved rule")
    return rule_dict


@app.delete("/rules/{port}", status_code=204)
async def remove_rule(port: int):
    delete_rule(port)
    audio_engine.update_rules(get_rules())


async def _spectrum_loop():
    """Broadcasts the latest FFT spectrum to all clients at ~30fps."""
    while True:
        await asyncio.sleep(1 / 30)
        bins = audio_engine.latest_spectrum
        if bins is None:
            continue
        message = json.dumps({"type": "spectrum", "bins": bins})
        async with _clients_lock:
            dead = set()
            for ws in _clients:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                _clients.discard(ws)


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
