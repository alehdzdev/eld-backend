#!/bin/sh

set -o errexit
set -o pipefail
set -o nounset

if [ -z "${POSTGRES_USER}" ]; then
  base_db_image_default_user='root'
  export POSTGRES_USER="${base_db_image_default_user}"
fi

postgres_ready() {
  python <<END
import sys
import psycopg2

try:
    psycopg2.connect(
      host="${POSTGRES_HOST}",
      user="${POSTGRES_USER}",
      password="${POSTGRES_PASSWORD}",
      dbname="${POSTGRES_DATABASE}",
      port=${POSTGRES_PORT},
    )
except psycopg2.OperationalError as error:
    print(error)
    sys.exit(-1)

sys.exit(0)
END
}
until postgres_ready; do
  echo >&2 'Waiting Postgres to become available...'
  sleep 1
done

echo >&2 'Postgres is available'

exec "$@"
