import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import SessionLocal, init_db
from .ingest.watcher import start_background
from .routers import auth, events, forecast, mlmodels, monitor, ppfg, reports, settings, wells
from .security import bootstrap_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
_s = get_settings()
app = FastAPI(title="ECD ML Monitoring", version="0.1.0",
              docs_url="/api/docs" if _s.docs_enabled else None,
              redoc_url=None, openapi_url="/api/openapi.json" if _s.docs_enabled else None)
_origins = [o.strip() for o in _s.cors_origins.split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

for r in (auth, wells, monitor, forecast, ppfg, events, mlmodels, settings, reports):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.on_event("startup")
def startup():
    s = get_settings()
    for d in (s.inbox_dir, s.upload_dir, s.model_dir, s.report_dir):
        Path(d).mkdir(parents=True, exist_ok=True)
    init_db()
    with SessionLocal() as db:
        bootstrap_admin(db)
    if s.watch_enabled:
        start_background()
