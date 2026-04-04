# Oliver's TODO (Backend — Python)

## Step 1: Project setup
- [ ] Create `backend/` folder and virtual environment
- [ ] Create `requirements.txt` with: `scapy`, `fastapi`, `uvicorn`, `numpy`, `scipy`, `pyaudio`, `watchdog`
- [ ] Install dependencies

## Step 2: Packet capture
- [ ] Use Scapy's `sniff()` to capture live packets
- [ ] Parse each packet into the schema fields: `timestamp`, `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol`, `flags`, `length`
- [ ] Print parsed packets to console to verify

## Step 3: FastAPI + WebSocket
- [ ] Stand up a FastAPI server
- [ ] Add a WebSocket endpoint that streams live packet messages (`type: "packet"`) to the frontend

## Step 4: Audio engine
- [ ] Generate base noise layers with PyAudio (white noise, wind, forest, fire)
- [ ] Apply per-packet frequency boosts using NumPy/SciPy
- [ ] Drive distortion when packet rate spikes (DoS/SYN flood detection)

## Step 5: Spectrum data
- [ ] Compute FFT on the audio buffer in real time (NumPy)
- [ ] Send `type: "spectrum"` messages over the WebSocket at ~30fps

## Step 6: Rules
- [ ] Add `POST /rules` REST endpoint to FastAPI
- [ ] Save received rules to `rules.json`
- [ ] Watch `rules.json` for changes (watchdog) and apply updated rules to the audio engine

## Step 7: Suspicious/malicious detection
- [ ] Detect SYN floods and other suspicious patterns
- [ ] Set `packet_type` to `"suspicious"` or `"malicious"` accordingly
- [ ] Trigger loud beep/horn sounds for flagged packets
