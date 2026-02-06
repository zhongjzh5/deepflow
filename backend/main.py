from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
import os

from pydantic import BaseModel
from typing import Optional
import json

import httpx
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from readability import Document
from pathlib import Path
from PIL import Image
import io

app = FastAPI(title="FastAPI Backend")

load_dotenv()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/hello")
def hello(name: str = "world"):
    return {"message": f"hello, {name}"}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class WeatherResponse(BaseModel):
    city: str
    latitude: float
    longitude: float
    temperature_c: Optional[float] = None
    windspeed_kmh: Optional[float] = None
    winddirection_deg: Optional[float] = None
    weathercode: Optional[int] = None
    time: Optional[str] = None


class ImageCrawlItem(BaseModel):
    id: str
    author: Optional[str] = None
    url: str
    download_url: str
    saved_path: Optional[str] = None


class ImageCrawlResponse(BaseModel):
    source: str
    count: int
    items: list[ImageCrawlItem]


def _get_weather(city: str) -> WeatherResponse:
    if not city.strip():
        raise HTTPException(status_code=400, detail="city is required")

    geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
    weather_url = "https://api.open-meteo.com/v1/forecast"

    try:
        with httpx.Client(timeout=30) as client:
            geo_resp = client.get(
                geocode_url,
                params={
                    "name": city,
                    "count": 1,
                    "language": "zh",
                    "format": "json",
                },
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Geocoding request error: {str(e)}")

    if geo_resp.status_code >= 400:
        raise HTTPException(status_code=geo_resp.status_code, detail=geo_resp.text)

    try:
        geo_data = geo_resp.json()
        results = geo_data.get("results") or []
        if not results:
            raise HTTPException(status_code=404, detail="city not found")
        place = results[0]
        lat = float(place["latitude"])
        lon = float(place["longitude"])
        resolved_name = place.get("name") or city
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Geocoding response parse error")

    try:
        with httpx.Client(timeout=30) as client:
            w_resp = client.get(
                weather_url,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": True,
                },
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Weather request error: {str(e)}")

    if w_resp.status_code >= 400:
        raise HTTPException(status_code=w_resp.status_code, detail=w_resp.text)

    try:
        w_data = w_resp.json()
        current = w_data.get("current_weather") or {}
        return WeatherResponse(
            city=resolved_name,
            latitude=lat,
            longitude=lon,
            temperature_c=current.get("temperature"),
            windspeed_kmh=current.get("windspeed"),
            winddirection_deg=current.get("winddirection"),
            weathercode=current.get("weathercode"),
            time=current.get("time"),
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Weather response parse error")


def _deepseek_chat(messages, tools=None, tool_choice=None):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing DEEPSEEK_API_KEY environment variable")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    url = f"{base_url}/v1/chat/completions"

    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
    }

    tool_image_crawl = {
        "type": "function",
        "function": {
            "name": "image_crawl",
            "description": "Get a list of random images from Picsum, optionally download a few to local disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "minimum": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 30},
                    "download": {"type": "boolean", "description": "Whether to download images"},
                    "download_count": {"type": "integer", "minimum": 0, "maximum": 10},
                    "width": {"type": "integer", "minimum": 50, "maximum": 2000},
                    "height": {"type": "integer", "minimum": 50, "maximum": 2000},
                },
                "required": [],
            },
        },
    }
    if tools is not None:
        body["tools"] = tools
    if tool_choice is not None:
        body["tool_choice"] = tool_choice

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=body, headers=headers)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"DeepSeek request error: {str(e)}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    try:
        return resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="DeepSeek response parse error")


def _serper_search(query: str, num_results: int = 5):
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing SERPER_API_KEY environment variable")

    if not query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    num = max(1, min(int(num_results), 10))
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    body = {"q": query, "num": num}

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=body, headers=headers)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Serper request error: {str(e)}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Serper response parse error")

    organic = data.get("organic") or []
    results = []
    for item in organic[:num]:
        results.append(
            {
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "position": item.get("position"),
            }
        )

    return {"query": query, "results": results}


def _web_read(url: str, max_chars: int = 6000):
    if not url.strip():
        raise HTTPException(status_code=400, detail="url is required")

    maxc = max(500, min(int(max_chars), 20000))

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DeepflowBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Web read request error: {str(e)}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type:
        text = resp.text
        text = text[:maxc]
        return {"url": url, "title": None, "content": text, "content_type": content_type}

    html = resp.text

    try:
        doc = Document(html)
        title = doc.short_title() or None
        article_html = doc.summary(html_partial=True)
        soup = BeautifulSoup(article_html, "html.parser")
        text = soup.get_text("\n", strip=True)
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string.strip() if soup.title and soup.title.string else None)
        text = soup.get_text("\n", strip=True)

    text = text[:maxc]
    return {"url": url, "title": title, "content": text, "content_type": content_type}


def _picsum_list(page: int = 1, limit: int = 10):
    p = max(1, int(page))
    l = max(1, min(int(limit), 30))
    url = "https://picsum.photos/v2/list"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, params={"page": p, "limit": l})
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Picsum list request error: {str(e)}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    try:
        return resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Picsum list parse error")


def _picsum_download(image_id: str, width: int = 800, height: int = 600, folder: str = "downloads/images"):
    img_id = str(image_id).strip()
    if not img_id:
        raise HTTPException(status_code=400, detail="image_id is required")

    w = max(50, min(int(width), 2000))
    h = max(50, min(int(height), 2000))

    # Allowlist domains for safety
    url = f"https://picsum.photos/id/{img_id}/{w}/{h}"

    base_dir = Path(__file__).resolve().parent
    out_dir = (base_dir / folder).resolve()
    # Ensure downloads stay within backend directory
    if base_dir not in out_dir.parents and out_dir != base_dir:
        raise HTTPException(status_code=400, detail="Invalid download folder")

    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"picsum_{img_id}_{w}x{h}.jpg"
    out_path = out_dir / filename

    # Size limit (bytes)
    max_bytes = 5 * 1024 * 1024

    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Picsum download request error: {str(e)}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    content = resp.content
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Image too large")

    # Validate it is an image (basic)
    try:
        Image.open(io.BytesIO(content)).verify()
    except Exception:
        raise HTTPException(status_code=502, detail="Downloaded content is not a valid image")

    out_path.write_bytes(content)
    return str(out_path)


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    tool_weather = {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather by city name (Chinese supported).",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. 北京, 上海, Shenzhen",
                    }
                },
                "required": ["city"],
            },
        },
    }

    tool_web_search = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for relevant pages and return a list of results with title/link/snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "num_results": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
            },
        },
    }

    tool_web_read = {
        "type": "function",
        "function": {
            "name": "web_read",
            "description": "Fetch a web page and extract the main readable text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer", "minimum": 500, "maximum": 20000},
                },
                "required": ["url"],
            },
        },
    }

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. If the user asks about weather, you may call tools.",
        },
        {"role": "user", "content": payload.message},
    ]

    tools = [tool_weather, tool_web_search, tool_web_read, tool_image_crawl]

    max_tool_rounds = 3
    for _ in range(max_tool_rounds):
        data = _deepseek_chat(messages=messages, tools=tools)

        try:
            msg = data["choices"][0]["message"]
        except Exception:
            raise HTTPException(status_code=502, detail="DeepSeek response parse error")

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            reply = msg.get("content") or ""
            return ChatResponse(reply=reply)

        messages.append(msg)

        for tc in tool_calls:
            fn = (tc.get("function") or {})
            name = fn.get("name")
            raw_args = fn.get("arguments") or "{}"

            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except Exception:
                args = {}

            if name == "get_weather":
                city = str(args.get("city", "")).strip()
                weather_obj = _get_weather(city)
                tool_content = weather_obj.model_dump_json(ensure_ascii=False)
            elif name == "web_search":
                query = str(args.get("query", "")).strip()
                num_results = args.get("num_results", 5)
                tool_content = json.dumps(_serper_search(query, num_results=num_results), ensure_ascii=False)
            elif name == "web_read":
                url = str(args.get("url", "")).strip()
                max_chars = args.get("max_chars", 6000)
                tool_content = json.dumps(_web_read(url, max_chars=max_chars), ensure_ascii=False)
            elif name == "image_crawl":
                page = args.get("page", 1)
                limit = args.get("limit", 10)
                download = bool(args.get("download", False))
                download_count = int(args.get("download_count", 0) or 0)
                width = args.get("width", 800)
                height = args.get("height", 600)

                pics = _picsum_list(page=page, limit=limit)
                items = []
                for it in pics:
                    items.append(
                        {
                            "id": str(it.get("id")),
                            "author": it.get("author"),
                            "url": it.get("url"),
                            "download_url": it.get("download_url"),
                            "saved_path": None,
                        }
                    )

                if download and download_count > 0:
                    for i in range(min(download_count, len(items), 10)):
                        img_id = items[i]["id"]
                        items[i]["saved_path"] = _picsum_download(img_id, width=width, height=height)

                tool_content = json.dumps(
                    {"source": "picsum", "count": len(items), "items": items},
                    ensure_ascii=False,
                )
            else:
                tool_content = json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": tool_content,
                }
            )

    return ChatResponse(reply="工具调用轮次已达上限，请简化问题或指定更具体的 URL/城市。")


@app.get("/api/weather", response_model=WeatherResponse)
def weather(city: str):
    return _get_weather(city)


@app.get("/api/image_crawl", response_model=ImageCrawlResponse)
def image_crawl(page: int = 1, limit: int = 10, download: bool = False, download_count: int = 0, width: int = 800, height: int = 600):
    pics = _picsum_list(page=page, limit=limit)
    items: list[ImageCrawlItem] = []
    for it in pics:
        items.append(
            ImageCrawlItem(
                id=str(it.get("id")),
                author=it.get("author"),
                url=it.get("url"),
                download_url=it.get("download_url"),
                saved_path=None,
            )
        )

    if download and download_count > 0:
        for i in range(min(int(download_count), len(items), 10)):
            items[i].saved_path = _picsum_download(items[i].id, width=width, height=height)

    return ImageCrawlResponse(source="picsum", count=len(items), items=items)

