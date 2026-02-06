# Backend (FastAPI)

## Run

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Env

Create `backend/.env` (it will be auto-loaded) and set:

- `DEEPSEEK_API_KEY=...`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-chat`
- `SERPER_API_KEY=...`

## Endpoints

- `GET /health`
- `GET /api/hello?name=...`
- `POST /api/chat` (DeepSeek + tools)
- `GET /api/weather?city=...` (Open-Meteo, no API key)

## Tool calling (weather)

In the chat UI, ask something like:

- "北京现在天气怎么样？"

The backend will let the model call the `get_weather` tool automatically.

## Tool calling (web search + reader)

In the chat UI, ask something like:

- "帮我搜索一下 DeepSeek function calling 的最佳实践，并给出处。"

The model can call:

- `web_search` (Serper)
- `web_read` (extract readable page content)
