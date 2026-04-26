# ByteSyndicate Challenge 4

Hackathon app for generating experiment plans from a scientific hypothesis.

- **Frontend:** React + Vite (`frontend/`)
- **Backend:** FastAPI (`main.py`)
- **AI provider:** OpenAI-compatible endpoint (key from `.env`)

## Prerequisites

- Python `3.10+`
- Node.js `18+` and npm

## Environment Setup

Create a root `.env` file:

```bash
OPENAI_API_KEY=your_key_here
```

Optional model overrides:

```bash
MODEL_NAME=gpt-4o
FALLBACK_MODEL_NAME=gpt-4o-mini
```

## Quick Start (Recommended)

1) Install frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

2) Start backend with safe port sync:

```bash
python dev_start.py
```

What this does:
- chooses a free backend port (prefers `8000-8008` and `8010`, then `8011-8100`)
- writes `frontend/.env.local` with the selected backend URL
- starts FastAPI on that same port

3) In another terminal, start frontend:

```bash
cd frontend
npm run dev
```

4) Open:

`http://localhost:5173`

## Judge Quick Start (60-second setup)

Use this when someone just cloned and wants a reliable demo quickly:

```bash
git clone https://github.com/Emirhann77/ByteSyndicate_Challange4.git
cd ByteSyndicate_Challange4
cd frontend && npm install && cd ..
python dev_start.py
```

In a second terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`.

### Important

- If `OPENAI_API_KEY` is present in root `.env`, the app uses live model generation.
- If API key is missing, the backend now uses a built-in **offline demo fallback** so the UI still generates a complete plan.
- No secrets are committed: `.env` and `.env.local` remain gitignored.

## Manual Backend Start (Alternative)

If you want a fixed port:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8010
```

Then set `frontend/.env.local`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8010
```

Restart Vite after changing `.env.local`.

## API Endpoints

- `GET /` service metadata
- `GET /health` health check
- `POST /generate-plan` generate a full plan
- `POST /suggest-hypothesis` generate a sample hypothesis

## Troubleshooting

- **"Unable to generate plan from scanned backends"**
  - Backend URL mismatch is likely. Re-run `python dev_start.py`, then restart Vite.
- **Port already in use**
  - Stop stale local processes using the same port, or let `dev_start.py` select a new one.
- **Model access / quota errors**
  - Verify `OPENAI_API_KEY` is valid and has quota.
- **`OPENAI_API_KEY` missing**
  - App still works in offline demo fallback mode, but outputs are template-style and not model-generated.
- **Frontend still using old config**
  - Hard refresh browser (`Ctrl+F5`) after backend URL changes.

## Notes

- `.env` and `.env.local` are intentionally ignored by git.
- `frontend/node_modules` should not be committed.