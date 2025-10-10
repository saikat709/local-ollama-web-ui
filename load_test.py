#!/usr/bin/env python3
# file: ndjson_load_test.py
import argparse
import asyncio
import json
import time
from typing import List

import aiohttp


DEFAULT_BODY = {
    "model": "llama3.1",
    "prompt": "Say hello and then count to ten.",
    "stream": True,
    "seed": 42,
    "num_predict": 10,
    "mirostat": 0,
    "temperature": 0.2,
    "top_k": 0,
    "top_p": 1.0,
    "typical_p": 1.0,
    "min_p": 0.0,
    "repeat_last_n": 64,
    "repeat_penalty": 1.05,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "penalize_newline": False,
    "stop": ["user:"],
    "num_ctx": 10,
    "num_keep": -1,
    "numa": False,
    "num_thread": 8,
    "num_batch": 128,
    "num_gpu": -1,
    "main_gpu": 0,
    "low_vram": False,
    "use_mmap": True,
    "use_mlock": False,
    "vocab_only": False,
    "options": {"num_predict": 512},
}

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/x-ndjson",
    "Accept-Encoding": "identity",  # avoid gzip to keep line boundaries simple
}


async def one_request(session: aiohttp.ClientSession, url: str, body: dict, verbose: bool = False):
    """
    Performs ONE streaming request, reading NDJSON lines via readline(),
    just like FastAPI's aiter_lines() on the server.
    """
    t0 = time.perf_counter()
    lines = 0
    bytes_read = 0
    ttfb = None
    had_text = False

    try:
        async with session.post(url, json=body, headers=HEADERS) as resp:
            if resp.status != 200:
                txt = await resp.text()
                return {"ok": False, "status": resp.status, "error": txt[:300]}

            # time to first byte occurs when we can read the first line (or any bytes)
            # read line-by-line until EOF
            while True:
                line_bytes = await resp.content.readline()
                if line_bytes == b"":  # EOF
                    break

                if ttfb is None:
                    ttfb = time.perf_counter() - t0

                # strip trailing newline, decode for possible JSON parse
                line = line_bytes.decode("utf-8", "ignore").rstrip("\r\n")
                if not line:
                    continue

                lines += 1
                bytes_read += len(line_bytes)

                if verbose:
                    print(line)

                # try to detect {"response": "..."} like your FE
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and obj.get("response"):
                        had_text = True
                except Exception:
                    pass

        total = time.perf_counter() - t0
        return {
            "ok": True,
            "status": 200,
            "ttfb": (ttfb if ttfb is not None else total),
            "total": total,
            "lines": lines,
            "bytes": bytes_read,
            "had_text": had_text,
        }

    except aiohttp.ClientPayloadError:
        # upstream closed early; treat as graceful end
        total = time.perf_counter() - t0
        return {"ok": True, "status": 200, "ttfb": (ttfb if ttfb else total), "total": total, "lines": lines, "bytes": bytes_read, "had_text": had_text}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)[:300]}


async def run(url: str, requests: int, concurrency: int, prompts: List[str], verbose: bool):
    # Connector with per-host limits; force_close avoids some chunked edge cases
    connector = aiohttp.TCPConnector(limit=concurrency, force_close=True, enable_cleanup_closed=True)
    timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_connect=10, sock_read=None)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        sem = asyncio.Semaphore(concurrency)
        results = []

        async def worker(i: int):
            async with sem:
                body = dict(DEFAULT_BODY)
                body["prompt"] = prompts[i % len(prompts)] if prompts else DEFAULT_BODY["prompt"]
                res = await one_request(session, url, body, verbose=verbose)
                results.append(res)

        tasks = [asyncio.create_task(worker(i)) for i in range(requests)]
        await asyncio.gather(*tasks)

    # summary
    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]
    print(f"\nURL: {url}")
    print(f"Requests: {len(results)}  |  Success: {len(ok)}  |  Failures: {len(fail)}")
    if fail:
        # show one example failure
        f = fail[0]
        print(f"Example failure -> status: {f.get('status')} error: {f.get('error')}")

    if ok:
        ttfb_vals = [r["ttfb"] for r in ok if "ttfb" in r]
        totals = [r["total"] for r in ok if "total" in r]
        lines = sum(r.get("lines", 0) for r in ok)
        bytes_read = sum(r.get("bytes", 0) for r in ok)
        had_text = sum(1 for r in ok if r.get("had_text"))

        def p(vals, q):
            vals = sorted(vals)
            if not vals:
                return None
            idx = int((len(vals) - 1) * q)
            return vals[idx]

        print(f"Lines read: {lines}  |  Bytes: {bytes_read}  |  Responses with text: {had_text}")
        print(f"TTFB p50: {p(ttfb_vals, 0.50):.3f}s  p95: {p(ttfb_vals, 0.95):.3f}s")
        print(f"Total p50: {p(totals, 0.50):.3f}s  p95: {p(totals, 0.95):.3f}s\n")


def main():
    ap = argparse.ArgumentParser(description="NDJSON line-by-line streaming load tester (aiohttp).")
    ap.add_argument("--url", default="http://10.100.201.91:8000/stream")
    ap.add_argument("-n", "--requests", type=int, default=1)
    ap.add_argument("-c", "--concurrency", type=int, default=1)
    ap.add_argument("--prompt", default=None, help="Single prompt")
    ap.add_argument("--prompts-file", default=None, help="File with one prompt per line")
    ap.add_argument("-v", "--verbose", action="store_true", help="Print each NDJSON line")
    args = ap.parse_args()

    # build prompts
    if args.prompts_file:
        with open(args.prompts_file, "r", encoding="utf-8") as f:
            prompts = [ln.strip() for ln in f if ln.strip()]
    else:
        prompts = [args.prompt] if args.prompt else [DEFAULT_BODY["prompt"]]

    asyncio.run(run(args.url, args.requests, args.concurrency, prompts, args.verbose))


if __name__ == "__main__":
    main()
