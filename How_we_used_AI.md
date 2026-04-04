# How We Used AI

## Claude (Anthropic)

| Activity | Description |
|----------|-------------|
| Work division | Divided project responsibilities between Oliver (backend) and James (frontend) based on the README |
| Architecture design | Designed the system architecture — WebSocket for packet stream and spectrum data, REST API for rules, SoundDevice running directly on the backend |
| Schema design | Defined the three data schemas (packet, spectrum, rule) and documented them in `schema.md` |
| Task planning | Generated prioritized TODO lists for both Oliver (`todo_oliver.md`) and James (`todo_james.md`) |
| Environment setup | Resolved PyAudio Windows build failure — switched from PyAudio/pipwin to SoundDevice; documented setup in `SETUP.md` |
| Git guidance | Advised on pulling without losing local changes (stash, commit ordering, push/pull workflow) |
| Packet sniffer scaffold | Generated `backend/sniffer.py` using Scapy `sniff()`, parsing packets into the agreed schema format |
