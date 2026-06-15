from __future__ import annotations

import os
import time
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from structlog.contextvars import bind_contextvars

from .agent import LabAgent
from .incidents import disable, enable, status
from .logging_config import configure_logging, get_logger, log_audit
from .metrics import record_error, snapshot
from .middleware import CorrelationIdMiddleware
from .pii import hash_user_id, summarize_text
from .schemas import ChatRequest, ChatResponse, ClientLatencyRequest
from .tracing import tracing_enabled

configure_logging()
log = get_logger()
app = FastAPI(title="Day 13 Observability Lab")
app.add_middleware(CorrelationIdMiddleware)
agent = LabAgent()


@app.on_event("startup")
async def startup() -> None:
    log.info(
        "app_started",
        service=os.getenv("APP_NAME", "day13-observability-lab"),
        env=os.getenv("APP_ENV", "dev"),
        payload={"tracing_enabled": tracing_enabled()},
    )


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tracing_enabled": tracing_enabled(), "incidents": status()}


@app.get("/metrics")
async def metrics() -> dict:
    return snapshot()


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    from pathlib import Path
    path = Path("dashboard.html")
    if path.exists():
        return HTMLResponse(content=path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Dashboard file not found")


@app.get("/api/logs")
async def get_api_logs() -> list[dict]:
    from pathlib import Path
    import json
    path = Path("data/logs.jsonl")
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
        if len(records) >= 100:
            break
    return records


@app.get("/api/audit")
async def get_api_audit() -> list[dict]:
    from pathlib import Path
    import json
    path = Path("data/audit.jsonl")
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
        if len(records) >= 100:
            break
    return records


@app.post("/api/client-latency")
async def record_client_latency(body: ClientLatencyRequest) -> dict:
    bind_contextvars(correlation_id=body.correlation_id)
    log.info(
        "client_latency_recorded",
        service="client",
        client_latency_ms=body.client_latency_ms,
    )
    return {"ok": True}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    start_time = time.perf_counter()
    user_id_hash = hash_user_id(body.user_id)
    # Cost optimization: route 'summary' feature requests to claude-haiku-4-5
    active_model = "claude-haiku-4-5" if body.feature == "summary" else agent.model
    
    # Enrich logs with request context (user_id_hash, session_id, feature, model, env)
    bind_contextvars(
        user_id_hash=user_id_hash,
        session_id=body.session_id,
        feature=body.feature,
        model=active_model,
        env=os.getenv("APP_ENV", "dev"),
    )
    
    # Write separate audit log entry
    log_audit(
        event="chat_request",
        user=user_id_hash,
        correlation_id=request.state.correlation_id,
        payload={
            "feature": body.feature,
            "session_id": body.session_id,
            "message_preview": summarize_text(body.message)
        }
    )
    
    log.info(
        "request_received",
        service="api",
        payload={"message_preview": summarize_text(body.message)},
    )
    try:
        result = agent.run(
            user_id=body.user_id,
            feature=body.feature,
            session_id=body.session_id,
            message=body.message,
            model=active_model,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        latency_ms_int = int(round(elapsed_ms))
        log.info(
            "response_sent",
            service="api",
            latency_ms=latency_ms_int,
            ttft_ms=result.ttft_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            cache_hit=result.cache_hit,
            payload={"answer_preview": summarize_text(result.answer)},
        )
        return ChatResponse(
            answer=result.answer,
            correlation_id=request.state.correlation_id,
            latency_ms=latency_ms_int,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
            cache_hit=result.cache_hit,
        )
    except Exception as exc:  # pragma: no cover
        error_type = type(exc).__name__
        record_error(error_type)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        latency_ms_int = int(round(elapsed_ms))
        log.error(
            "request_failed",
            service="api",
            error_type=error_type,
            latency_ms=latency_ms_int,
            cache_hit=False,
            payload={"detail": str(exc), "message_preview": summarize_text(body.message)},
        )
        raise HTTPException(status_code=500, detail=error_type) from exc


@app.post("/incidents/{name}/enable")
async def enable_incident(name: str) -> JSONResponse:
    try:
        enable(name)
        log_audit(
            event="incident_enabled",
            user="admin",
            correlation_id="control-plane",
            payload={"incident_name": name}
        )
        log.warning("incident_enabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/incidents/{name}/disable")
async def disable_incident(name: str) -> JSONResponse:
    try:
        disable(name)
        log_audit(
            event="incident_disabled",
            user="admin",
            correlation_id="control-plane",
            payload={"incident_name": name}
        )
        log.warning("incident_disabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
