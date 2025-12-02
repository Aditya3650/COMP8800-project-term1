# src/main.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.shared.storage import fetch_latest, fetch_stats
import traceback, json, asyncio, time, logging


logging.basicConfig(level=logging.INFO)

gen_lock = asyncio.Lock()  # <-- one generation at a time


# ✅ point to src/dashboard/templates
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI()

import asyncio

@app.on_event("startup")
async def preload_llm():
    try:
        from src.llm_infer import _load_once
        await asyncio.to_thread(_load_once)   # load base+adapter once in background
        print("[app] LLM preloaded")
    except Exception as e:
        print("[app] LLM preload skipped:", e)


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
    
@app.get("/api/triage/_health")
def api_triage_health():
    # Try import + build input for a tiny sample without generating
    try:
        from src.llm_infer import ADAPTER_DIR, _load_once  # type: ignore
        _load_once()  # just ensures model + tokenizer load
        return {"ok": True, "adapter_dir": str(ADAPTER_DIR)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e), "trace": traceback.format_exc()}, status_code=500)

@app.post("/api/triage")
async def api_triage(row: dict):
    try:
        from src.llm_infer import build_input_from_row, generate_triage  # lazy import
    except Exception as e:
        return JSONResponse({"error": f"LLM not ready: {e}"}, status_code=500)

    t0 = time.time()
    logging.info("triage start")
    try:
        input_str = build_input_from_row(row)

        async with gen_lock:   # serialize heavy CPU work
            out = await asyncio.wait_for(
                asyncio.to_thread(generate_triage, input_str),
                timeout=180   # backend timeout in seconds
            )

        logging.info("triage done in %.1fs", time.time() - t0)
        return {"input": input_str, "output": out}
    except asyncio.TimeoutError:
        logging.warning("triage TIMEOUT after %.1fs", time.time() - t0)
        return JSONResponse(
            {"error": "Triage timed out on CPU. Try again; model may still be warming."},
            status_code=504,
        )
    except Exception as e:
        logging.exception("triage error")
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)
