# file_browser.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import urllib.parse
import mimetypes

ROOT = Path("./srv/public_files").resolve()  # <-- change to your folder

app = FastAPI(title="Public File Browser")

# Optional: mount a /raw path to serve static files efficiently
app.mount("/raw", StaticFiles(directory=str(ROOT), html=False), name="raw")

def safe_join(root: Path, rel: str) -> Path:
    # Avoid path traversal
    target = (root / rel).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(403, "Forbidden")
    return target

def icon(name: str, is_dir: bool) -> str:
    return "📁" if is_dir else "📄"

def fmt_size(p: Path) -> str:
    try:
        b = p.stat().st_size
    except Exception:
        return "-"
    for unit in ["B","KB","MB","GB","TB"]:
        if b < 1024:
            return f"{b:.0f} {unit}"
        b /= 1024
    return f"{b:.0f} PB"

def breadcrumb(rel: str) -> str:
    parts = [p for p in Path(rel).parts if p]
    crumbs = ['<a href="/">/</a>']
    cur = ""
    for part in parts:
        cur = f"{cur}/{part}" if cur else part
        crumbs.append(f'<a href="/browse/{urllib.parse.quote(cur)}">{part}</a>')
    return " / ".join(crumbs)

@app.get("/", response_class=HTMLResponse)
async def root():
    # redirect to browse root
    return ('<meta http-equiv="refresh" content="0; url=/browse/">'
            '<a href="/browse/">Open file browser</a>')

@app.get("/browse/", response_class=HTMLResponse)
@app.get("/browse/{rel_path:path}", response_class=HTMLResponse)
async def browse(rel_path: str = ""):
    target = safe_join(ROOT, rel_path)
    if not target.exists():
        raise HTTPException(404, "Not found")

    # If it's a file, serve it directly
    if target.is_file():
        # Use /raw for efficient static serving (supports range, proper headers)
        # but we can also use FileResponse here:
        return FileResponse(path=str(target), filename=target.name)

    # Directory listing
    entries = []
    # Parent link
    if rel_path:
        parent = str(Path(rel_path).parent)
        href = "/browse/" + urllib.parse.quote(parent) if parent != "." else "/browse/"
        entries.append(f'<tr><td>⬆️</td><td><a href="{href}">..</a></td><td></td></tr>')

    for p in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        name = p.name
        rel = str(Path(rel_path) / name) if rel_path else name
        href = "/browse/" + urllib.parse.quote(rel)
        entries.append(
            f"<tr>"
            f"<td>{icon(name, p.is_dir())}</td>"
            f"<td><a href='{href}'>{name}</a></td>"
            f"<td style='text-align:right'>{'' if p.is_dir() else fmt_size(p)}</td>"
            f"</tr>"
        )

    page = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>Index of /{rel_path}</title>
      <style>
        body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 10px; border-bottom: 1px solid #eee; }}
        a {{ text-decoration: none; color: #0366d6; }}
        a:hover {{ text-decoration: underline; }}
        .crumbs {{ margin-bottom: 12px; color: #555; }}
        .wrap {{ max-width: 1000px; margin: auto; }}
        td:first-child {{ width: 2rem; }}
        td:last-child {{ width: 7rem; color: #666; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="crumbs">{breadcrumb(rel_path)}</div>
        <h3>Index of /{rel_path}</h3>
        <table>
          <thead><tr><th></th><th>Name</th><th style="text-align:right">Size</th></tr></thead>
          <tbody>
            {''.join(entries) if entries else '<tr><td></td><td><em>Empty</em></td><td></td></tr>'}
          </tbody>
        </table>
        <p style="color:#777; font-size: 12px;">Served by FastAPI • Public read-only</p>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(page)
