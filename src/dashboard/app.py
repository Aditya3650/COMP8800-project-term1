# src/dashboard/app.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
from shared.storage import fetch_latest, fetch_stats

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@app.get("/api/events")
def api_events(limit: int = 100, log: str | None = None, event_id: int | None = None):
    logs = [s.strip() for s in log.split(",")] if log else None
    rows = fetch_latest(limit=limit, log_types=logs, event_id=event_id)
    return JSONResponse({"items": rows, "count": len(rows)})

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, limit: int = Query(50), log: str | None = None, event_id: int | None = None):
    logs = [s.strip() for s in log.split(",")] if log else None
    stats, total = fetch_stats()
    rows = fetch_latest(limit=limit, log_types=logs, event_id=event_id)


    interesting = {4625, 4672, 7045, 1102}
    for r in rows:
        r["flag"] = (r["event_id"] in interesting)

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats, "total_events": total, "rows": rows}
    )
