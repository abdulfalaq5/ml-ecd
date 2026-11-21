#!/usr/bin/env sh
# Backup database + file aplikasi (upload, model, laporan) ke ./backups/<tanggal>/
# Pakai: ./scripts/backup.sh
set -eu
cd "$(dirname "$0")/.."
. ./.env 2>/dev/null || true
OUT="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "1/3 dump database…"
docker compose exec -T db pg_dump -U "${DB_USER:-ecd}" -d "${DB_NAME:-ecd}" -Fc > "$OUT/ecd.dump"
echo "2/3 arsip file aplikasi (/data: uploads, models, reports)…"
docker compose run --rm --no-deps -v "$PWD/$OUT:/backup" --entrypoint sh backend \
  -c "tar czf /backup/appdata.tgz -C /data --exclude=./inbox ."
echo "3/3 salin konfigurasi…"
cp .env "$OUT/env.backup"
ls -lh "$OUT"
echo "Selesai: $OUT"
