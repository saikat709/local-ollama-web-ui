from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel
import os, json, httpx, asyncio

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

app = FastAPI(title="Ollama Proxy")

class GenerateReq(BaseModel):
    model: str = "llama3.1"
    prompt: str
    stream: bool = True

# --- Non-streamed (one JSON) ---
@app.post("/generate")
async def generate(req: GenerateReq):
    payload = req.model_dump()
    payload["stream"] = False
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        return JSONResponse({"response": data.get("response", "")})

# --- Streamed (NDJSON from Ollama -> plain text tokens) ---
@app.post("/stream")
async def stream(req: GenerateReq):
    payload = req.model_dump()
    payload["stream"] = True

    async def token_generator():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{OLLAMA_BASE}/api/generate", json=payload) as r:
                if r.status_code != 200:
                    body = await r.aread()
                    raise HTTPException(r.status_code, body.decode("utf-8", "ignore"))
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("done"):     # <— ignore the final empty chunk
                            break
                        chunk = obj.get("response", "")
                        if chunk:
                            yield chunk
                            await asyncio.sleep(0)  # let loop breathe
                    except json.JSONDecodeError:
                        continue
    return StreamingResponse(token_generator(), media_type="text/plain")

# --- Quick health check ---
@app.get("/healthz")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
        return PlainTextResponse("ok")
    except Exception as e:
        raise HTTPException(503, str(e))
