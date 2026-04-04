# NoiseSniffer Data Schemas

## WebSocket Messages (Backend → Frontend)

### Packet
Sent per captured packet for the live packet stream (Tab 1).
```json
{
  "type": "packet",
  "timestamp": "2026-04-04T12:00:00.000Z",
  "src_ip": "192.168.1.1",
  "dst_ip": "192.168.1.2",
  "src_port": 443,
  "dst_port": 52300,
  "protocol": "TCP",
  "flags": "SYN",
  "length": 60,
  "packet_type": "normal"
}
```
- `protocol`: `"TCP"`, `"UDP"`, `"ICMP"`, etc.
- `flags`: TCP flags string (e.g. `"SYN"`, `"ACK"`, `"SYN-ACK"`), `null` for non-TCP
- `packet_type`: `"normal"`, `"suspicious"`, or `"malicious"`

### Spectrum
Sent at ~30fps for the spectrum analyzer (Tab 2).
```json
{
  "type": "spectrum",
  "bins": [0.1, 0.4, 0.9, 0.6, 0.2]
}
```
- `bins`: array of amplitudes (0.0–1.0), one per frequency band

---

## REST API (Frontend → Backend)

### Rule
`POST /rules` — create or update a rule.
```json
{
  "port": 443,
  "ip_whitelist": ["192.168.1.1", "10.0.0.5"],
  "sound": "piano",
  "sound_type": "A4",
  "frequency_boost": 1.5
}
```
- `ip_whitelist`: list of IPs this rule applies to; empty list `[]` means all IPs
- `sound`: `"synth"` (default) for a synthesized sine burst, or `"piano"` to play a pre-loaded OGG piano sample
- `sound_type`: musical note name including sharps, e.g. `"A4"`, `"C#4"`; supported range `"C3"`–`"B5"` (36 chromatic notes)
- `frequency_boost`: amplitude multiplier (1.0 = neutral)
