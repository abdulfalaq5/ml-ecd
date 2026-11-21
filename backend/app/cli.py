"""Impor massal dari baris perintah.

  docker compose exec backend python -m app.cli import /data/inbox/"PDSI 53.2" --well "PDSI 53.2"
  docker compose exec backend python -m app.cli scan
"""
import argparse
from pathlib import Path

from .db import SessionLocal, init_db
from .ingest.service import get_or_create_well, ingest_bytes
from .ingest.watcher import scan_once

EXT = {".las", ".csv", ".zip", ".txt"}


def main():
    ap = argparse.ArgumentParser(prog="app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    im = sub.add_parser("import")
    im.add_argument("path")
    im.add_argument("--well", required=True)
    im.add_argument("--mode", default="append", choices=["append", "replace"])
    im.add_argument("--force", action="store_true", help="proses ulang file yang sudah pernah di-ingest")
    sub.add_parser("scan")
    a = ap.parse_args()
    init_db()
    if a.cmd == "scan":
        for r in scan_once():
            print(r)
        return
    p = Path(a.path)
    files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.suffix.lower() in EXT)
    with SessionLocal() as db:
        w = get_or_create_well(db, a.well)
        for f in files:
            for r in ingest_bytes(db, w, f.name, f.read_bytes(), "cli", a.mode, force=a.force):
                print(f"{f.name}: {r.get('status')} rec={r.get('record')} rows={r.get('rows')} {r.get('message', '')}")


if __name__ == "__main__":
    main()
