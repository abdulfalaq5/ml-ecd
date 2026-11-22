#!/usr/bin/env bash
# Jalankan bending_estimate.py di container backend (pandas + parser + modul app/core/bending.py ada di sana).
#   tools/bending/run.sh --list-catalog
#   tools/bending/run.sh --example-runs runs.json
#   tools/bending/run.sh --well "BDSI 18" --runs runs.json --calibrate --out bending_out
#   tools/bending/run.sh --well GW339 --preset CSG_7_RUN --from "2026-11-11 00:00" --to "2026-11-12 19:30" --setting-depth 5354
#   tools/bending/run.sh --survey rec07.las --rig rec01_a.las rec01_b.las --mw rec04.las --preset BHA_8.5_STD
# File input di host hanya DISALIN ke container (file asli tidak dipindah). Katalog: backend/app/bending_catalog.json
# (selalu dikirim dari repo, jadi edit katalog langsung berlaku tanpa build ulang), atau --catalog file lain.
set -euo pipefail
cd "$(dirname "$0")/../.."
W=/tmp/bending_run
dc() { docker compose exec -T "$@"; }
put() { local b="in/$(basename "$1" | tr ' ' _)"; dc backend sh -c "cat > '$W/$b'" < "$1"; echo "$W/$b"; }

dc backend sh -c "rm -rf $W && mkdir -p $W/in"
docker compose cp tools/bending/bending_estimate.py "backend:$W/bending_estimate.py" >/dev/null 2>&1
args=(--catalog "$(put backend/app/bending_catalog.json)")
out=bending_out example=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) out="$2"; shift 2 ;;
    --example-runs) example="$2"; args+=(--example-runs "$W/in/example_runs.json"); shift 2 ;;
    --list-catalog|--calibrate) args+=("$1"); shift ;;
    --well|--tz|--step|--from|--to|--setting-depth|--preset|--shoe) args+=("$1" "$2"); shift 2 ;;
    --catalog|--survey|--mw|--string|--runs) args+=("$1" "$(put "$2")"); shift 2 ;;
    --rig) args+=(--rig); shift
      while [[ $# -gt 0 && "$1" != --* ]]; do args+=("$(put "$1")"); shift; done ;;
    *) args+=("$1"); shift ;;
  esac
done

if [[ -n "$example" ]]; then
  dc -w /app backend python "$W/bending_estimate.py" "${args[@]}" >/dev/null
  dc backend cat "$W/in/example_runs.json" > "$example"
  echo "contoh runs ditulis: $example"
elif [[ " ${args[*]} " == *" --list-catalog "* ]]; then
  dc -w /app backend python "$W/bending_estimate.py" "${args[@]}"
else
  dc -w /app backend python "$W/bending_estimate.py" "${args[@]}" --out "$W/out" 2>&1 | grep -v Warning || true
  if dc backend test -d "$W/out"; then
    mkdir -p "$out"
    docker compose cp "backend:$W/out/." "$out/" >/dev/null 2>&1
    echo "hasil disalin ke: $out/"
  fi
fi
dc backend rm -rf "$W"
