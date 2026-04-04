# James's TODO (Frontend — React)

## Step 1: Project setup
- [ ] Scaffold React app (`npx create-react-app` or Vite) in `frontend/`
- [ ] Install dependencies (charting library TBD for Tab 2)

## Step 2: Tab shell
- [ ] Build three-tab layout: Packet Stream, Spectrum Analyzer, Rules Editor

## Step 3: WebSocket connection
- [ ] Create a WebSocket hook that connects to the backend
- [ ] Parse incoming messages by `type` field (`"packet"` vs `"spectrum"`)
- [ ] Mock data for both types so development isn't blocked by the backend

## Step 4: Tab 1 — Packet stream
- [ ] Render a live-updating table with packet fields: timestamp, src/dst IP, src/dst port, protocol, flags, length, packet_type
- [ ] Highlight rows for `"suspicious"` and `"malicious"` packets

## Step 5: Tab 3 — Rules editor
- [ ] Build rule form: port, IP whitelist, sound type, frequency boost
- [ ] `POST /rules` to the backend when a rule is saved
- [ ] List existing rules, allow editing/deleting
- [ ] Save rules to a local JSON file

## Step 6: Tab 2 — Spectrum analyzer (stretch goal)
- [ ] Choose and integrate a charting library for real-time frequency visualization
- [ ] Render `bins` array from `"spectrum"` WebSocket messages as EQ bars
- [ ] Show labeled frequency bands per port/rule
