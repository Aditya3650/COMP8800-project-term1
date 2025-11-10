# src/main.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.shared.storage import fetch_latest, fetch_stats
import traceback, json, asyncio

# ✅ point to src/dashboard/templates
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI()

@app.get("/api/events")
def api_events(limit: int = 100, log: str | None = None, event_id: int | None = None):
    logs = [s.strip() for s in log.split(",")] if log else None
    rows = fetch_latest(limit=limit, log_types=logs, event_id=event_id)
    return JSONResponse({"items": rows, "count": len(rows)})

@app.post("/api/triage")
def api_triage(row: dict):
    """
    On-demand triage for a row like those returned by /api/events
    {log_type, time, event_id, source, message: [...]}
    """
    try:
        # Lazy-import LLM so the app can start even if torch/transformers aren't installed yet
        from src.llm_infer import build_input_from_row, generate_triage  # type: ignore
    except Exception as e:
        return JSONResponse(
            {"error": f"LLM not ready: {e}. Install deps and place adapter folder."},
            status_code=500
        )
    try:
        input_str = build_input_from_row(row)
        output = generate_triage(input_str)
        return JSONResponse({"input": input_str, "output": output})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

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

    try:
        input_str = build_input_from_row(row)

        # run generation in a worker, guarded by a timeout (e.g., 25s)
        async def _work():
            return await asyncio.to_thread(generate_triage, input_str)

        out = await asyncio.wait_for(_work(), timeout=25)
        return {"input": input_str, "output": out}
    except asyncio.TimeoutError:
        return JSONResponse({"error": "Triage timed out (model is likely still loading). Try the Health button, then retry."}, status_code=504)
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)