# Setup Guide

## Prerequisites
- Python 3.10+
- [pipenv](https://pipenv.pypa.io/en/latest/) (`pip install pipenv`)
- Node.js + [pnpm](https://pnpm.io/) (`pnpm install -g pnpm`)

---

## Backend (Python)

### 1. Navigate to the backend folder
```bash
cd backend
```

### 2. Install dependencies
```bash
pipenv install
```

### 3. Activate the environment
```bash
pipenv shell
```

### 4. Start the server
```bash
uvicorn main:app --reload
```

WebSocket endpoint: `ws://localhost:8000/ws`

---

## Frontend (React)

### 1. Navigate to the frontend folder
```bash
cd frontend
```

### 2. Install dependencies
```bash
pnpm install
```

### 3. Start the dev server
```bash
pnpm dev
```

---

## Running the App

Start the backend first, then the noise-sniffer:
```bash
# Terminal 1 — backend
cd backend
pipenv shell
uvicorn main:app --reload

# Terminal 2 — noise-sniffer
cd noise-sniffer
pnpm dev
```
