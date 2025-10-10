from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import os, json, httpx, asyncio

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

app = FastAPI(title="Ollama Proxy")

# Allow all CORS (for testing only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/generate")
async def generate(req: Request):
    payload = await req.json()
    payload["stream"] = False
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        return JSONResponse({"response": data.get("response", "")})


@app.post("/stream")
async def stream(request: Request):
    payload = await request.json()
    payload.setdefault("stream", True)

    async def ndjson():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{OLLAMA_BASE}/api/generate", json=payload) as r:
                if r.status_code != 200:
                    body = await r.aread()
                    raise HTTPException(r.status_code, body.decode("utf-8", "ignore"))
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    yield line + "\n"

    return StreamingResponse(ndjson(), media_type="application/x-ndjson")


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


## Run
# pip3 install fastapi uvicorn httpx
# python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload