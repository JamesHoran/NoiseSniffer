import asyncio
import json
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from scapy.all import sniff, conf as scapy_conf
from sniffer import parse_packet

IFACE = r"\Device\NPF_{D1E60D1D-DACE-48C1-9915-47A46F14DFF0}"

app = FastAPI()

# All active WebSocket connections
_clients: set[WebSocket] = set()
_clients_lock = asyncio.Lock()

# Bridge from sync Scapy thread → async event loop
_loop: asyncio.AbstractEventLoop | None = None
_queue: asyncio.Queue = asyncio.Queue()


def _on_packet(packet):
    parsed = parse_packet(packet)
    if parsed and _loop is not None:
        _loop.call_soon_threadsafe(_queue.put_nowait, json.dumps(parsed))


def _start_sniffer():
    scapy_conf.verb = 0
    sniff(iface=IFACE, filter="ip", prn=_on_packet, store=False)


@app.on_event("startup")
async def startup():
    global _loop
    _loop = asyncio.get_running_loop()
    t = threading.Thread(target=_start_sniffer, daemon=True)
    t.start()
    asyncio.create_task(_broadcast_loop())


async def _broadcast_loop():
    while True:
        message = await _queue.get()
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
    await ws.accept()
    async with _clients_lock:
        _clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keep connection alive; ignore client messages
    except WebSocketDisconnect:
        pass
    finally:
        async with _clients_lock:
            _clients.discard(ws)
