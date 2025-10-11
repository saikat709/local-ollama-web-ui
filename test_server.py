
from __future__ import annotations

import argparse
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

servers = [
    {
        'name' : 'Sakib Vai PC',
        'ip' : '10.47.0.140',
        'port' : '8000',
        'current_load' : 0, 
        'is_active' : True
    },
    {
        'name': 'Tausif Vai PC',
        'ip': '10.100.201.127',
        'port': '8000',
        'current_load': 0,
        'is_active': True,
    },
    {
        'name' : 'Darun Nayeem Laptop',
        'ip' : '10.100.200.236',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    },
    {
        'name' : 'Server Pc 1',
        'ip' : '10.42.0.155',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    },
    {
        'name' : 'Arif Vai PC',
        'ip' : '10.47.0.136',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    },
    {
        'name' : 'Proma Apu PC',
        'ip' : '10.47.0.109',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    },
    {
        'name' : 'Nahid Vai PC Left',
        'ip' : '10.47.0.105',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    },
    {
        'name' : 'Dipshika Apu PC',
        'ip' : '10.47.0.130',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    },
    {
        'name' : 'Ratul PC',
        'ip' : '10.100.202.164',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    },
    {
        'name' : 'Akkhar PC',
        'ip' : '10.100.202.160',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    },
     {
        'name' : 'Nafis PC',
        'ip' : '10.100.202.173',
        'port' : '8000',
        'current_load' : 0,
        'is_active' : True
    }
]

"""
Simple health check script for the servers above. It will query each server's
`/healthz` endpoint and print a short log line for each.

Features:
- Synchronous and concurrent checks (default: concurrent)
- Optional JSON output (--json)
- Returns non-zero exit code if --fail-on-unhealthy and any server is unhealthy

Usage:
  python3 test_server.py            # run with defaults
  python3 test_server.py --timeout 2 --json

This file intentionally uses only the Python standard library so it can run
without extra dependencies.
"""


def check_server(server: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
    """Check the /healthz endpoint of a single server.

    Returns a dict with keys: server, url, status_code, body, ok, elapsed
    """
    url = f"http://{server['ip']}:{server['port']}/healthz"
    start = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body_bytes = resp.read()
            try:
                body = body_bytes.decode("utf-8", errors="ignore").strip()
            except Exception:
                body = repr(body_bytes)
            code = resp.getcode()
            # consider 200 as OK; if body contains common OK words treat as OK too
            ok = code == 200 and (body == "" or body.lower() in ("ok", "okay", "healthy"))
            elapsed = time.time() - start
            server["is_active"] = bool(ok)
            return {
                "server": server.get("name"),
                "url": url,
                "status_code": code,
                "body": body,
                "ok": ok,
                "elapsed": elapsed,
            }
    except Exception as e:
        elapsed = time.time() - start
        server["is_active"] = False
        return {
            "server": server.get("name"),
            "url": url,
            "status_code": None,
            "body": str(e),
            "ok": False,
            "elapsed": elapsed,
        }


def run_checks(servers: List[Dict[str, Any]], timeout: float = 5.0, concurrent: bool = True) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if concurrent:
        with ThreadPoolExecutor(max_workers=min(32, len(servers) or 1)) as ex:
            futures = {ex.submit(check_server, s, timeout): s for s in servers}
            for fut in as_completed(futures):
                results.append(fut.result())
    else:
        for s in servers:
            results.append(check_server(s, timeout))
    return results


def format_result(r: Dict[str, Any]) -> str:
    if r["ok"]:
        return f"[OK]   {r['server']:20} {r['url']:30} ({r['elapsed']:.2f}s) -> {r['body']}"
    else:
        code = r['status_code'] or "ERR"
        return f"[FAIL] {r['server']:20} {r['url']:30} ({r['elapsed']:.2f}s) -> {code} {r['body']}"


def main() -> int:
    p = argparse.ArgumentParser(description="Check /healthz for a list of servers")
    p.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    p.add_argument("--no-concurrent", dest="concurrent", action="store_false", help="Disable concurrent checks")
    p.add_argument("--json", action="store_true", help="Output results as JSON")
    p.add_argument("--fail-on-unhealthy", action="store_true", help="Exit with non-zero if any server is unhealthy")
    args = p.parse_args()

    results = run_checks(servers, timeout=args.timeout, concurrent=args.concurrent)

    if args.json:
        import json

        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(format_result(r))

    any_unhealthy = any(not r["ok"] for r in results)
    if args.fail_on_unhealthy and any_unhealthy:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

