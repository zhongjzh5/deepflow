# Fullstack Template (FastAPI + Vue)

## Structure

- `backend/`: FastAPI
- `frontend/`: Vue (Vite)

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.
