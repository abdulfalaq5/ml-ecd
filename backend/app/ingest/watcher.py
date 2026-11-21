"""Folder dipantau: /data/inbox/<nama sumur>/**/*.zip|las|csv -> ingest otomatis (mode tambah)."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from ..config import get_settings
from ..db import SessionLocal
from .service import get_or_create_well, ingest_bytes

log = logging.getLogger("watcher")
EXT = {".zip", ".las", ".csv"}
_lock = threading.Lock()


def _state_path() -> Path:
    return Path(get_settings().upload_dir) / ".watch_state.json"


def _load() -> dict:
    p = _state_path()
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def scan_once() -> list[dict]:
    """Proses file baru/berubah. Nama folder level-1 di inbox = nama sumur."""
    s = get_settings()
    root = Path(s.inbox_dir)
    if not root.is_dir():
        return []
    with _lock:
        state = _load()
        done = []
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in EXT or f.name.startswith("."):
                continue
            rel = f.relative_to(root)
            if len(rel.parts) < 2:
                continue  # file harus di dalam folder sumur
            st = f.stat()
            sig = f"{st.st_size}:{int(st.st_mtime)}"
            if state.get(str(rel)) == sig:
                continue
            well_name = rel.parts[0]
            db = SessionLocal()
            try:
                well = get_or_create_well(db, well_name)
                res = ingest_bytes(db, well, f.name, f.read_bytes(), "watcher", "append")
                done.append({"path": str(rel), "well": well_name, "results": res})
                log.info("watcher: %s -> %s", rel, [r.get("status") for r in res])
            except Exception:  # noqa: BLE001
                log.exception("watcher gagal: %s", rel)
            finally:
                db.close()
            state[str(rel)] = sig
            Path(s.upload_dir).mkdir(parents=True, exist_ok=True)
            _state_path().write_text(json.dumps(state, indent=0))
        return done


def start_background() -> None:
    s = get_settings()
    if not s.watch_enabled:
        return

    def loop():
        time.sleep(5)
        while True:
            try:
                scan_once()
            except Exception:  # noqa: BLE001
                log.exception("watcher loop")
            time.sleep(max(10, s.watch_interval_s))

    threading.Thread(target=loop, name="inbox-watcher", daemon=True).start()
