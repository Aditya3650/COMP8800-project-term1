# src/dashboard/app.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

DATA_DIR = Path(__file__).resolve().parents[1]  # .../src
FILES = {
    "System": DATA_DIR / "system_logs.json",
    "Security": DATA_DIR / "security_logs.json",
    "Application": DATA_DIR / "application_logs.json",
}

def load_logs():
    out = {}
    for name, path in FILES.items():
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {"metadata": {"log_type": name, "total_records_saved": 0}, "events": []}
        else:
            data = {"metadata": {"log_type": name, "total_records_saved": 0}, "events": []}
        out[name] = data
    return out

@app.get("/api/events")
def api_events():
    """Return all events and metadata (small prototype; not paginated)."""
    return JSONResponse(load_logs())

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    data = load_logs()

    # quick stats
    stats = []
    total_events = 0
    for log_type, blob in data.items():
        meta = blob.get("metadata", {})
        count = meta.get("total_records_saved", 0)
        total_events += count
        stats.append({
            "log_type": log_type,
            "count": count,
            "range": f"{meta.get('oldest_log','N/A')} → {meta.get('newest_log','N/A')}"
        })

    # show the latest few events across logs (newest timestamp first)
    def parse_time(s):
        try:
            # your JSON uses "YYYY-MM-DD HH:MM:SS"
            return datetime.fromisoformat(s)
        except Exception:
            return datetime.min

    latest_rows = []
    for log_type, blob in data.items():
        for ev in blob.get("events", []):
            latest_rows.append({
                "log_type": log_type,
                "time": ev.get("Time"),
                "event_id": ev.get("EventID"),
                "source": ev.get("Source"),
                "message": (ev.get("Message") or [])[:3]  # preview first few inserts
            })
    latest_rows.sort(key=lambda r: parse_time(r["time"]), reverse=True)
    latest_rows = latest_rows[:50]  # keep it light

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats, "total_events": total_events, "rows": latest_rows}
    )
