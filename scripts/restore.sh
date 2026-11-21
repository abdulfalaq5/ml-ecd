#!/usr/bin/env sh
# Pulihkan backup ke instalasi ini (DATA LAMA DI SERVER INI DITIMPA).
# Pakai: ./scripts/restore.sh backups/20261121_120000
set -eu
cd "$(dirname "$0")/.."
SRC="${1:?folder backup, mis. backups/20261121_120000}"
[ -f "$SRC/ecd.dump" ] || { echo "ecd.dump tidak ada di $SRC"; exit 1; }
. ./.env 2>/dev/null || true
printf "Data di server ini akan ditimpa dari %s. Lanjut? [y/N] " "$SRC"; read ans; [ "$ans" = "y" ] || exit 1
docker compose up -d db
echo "menunggu database…"
until docker compose exec -T db pg_isready -U "${DB_USER:-ecd}" >/dev/null 2>&1; do sleep 2; done
docker compose stop backend frontend 2>/dev/null || true
echo "1/2 restore database…"
docker compose exec -T db psql -U "${DB_USER:-ecd}" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME:-ecd};" -c "CREATE DATABASE ${DB_NAME:-ecd};"
docker compose exec -T db psql -U "${DB_USER:-ecd}" -d "${DB_NAME:-ecd}" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" -c "SELECT timescaledb_pre_restore();"
docker compose exec -T db pg_restore -U "${DB_USER:-ecd}" -d "${DB_NAME:-ecd}" --no-owner < "$SRC/ecd.dump" || true
docker compose exec -T db psql -U "${DB_USER:-ecd}" -d "${DB_NAME:-ecd}" -c "SELECT timescaledb_post_restore();"
echo "2/2 restore file aplikasi…"
if [ -f "$SRC/appdata.tgz" ]; then
  docker compose run --rm --no-deps -v "$PWD/$SRC:/backup" --entrypoint sh backend -c "tar xzf /backup/appdata.tgz -C /data"
fi
docker compose up -d
echo "Selesai. Buka http://<server>:${WEB_PORT:-8080}"
