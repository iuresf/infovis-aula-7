#!/bin/sh
set -eu
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=metabase_db="${METABASE_DB:-metabase}" <<'SQL'
SELECT format('CREATE DATABASE %I', :'metabase_db')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'metabase_db')\gexec
SQL
