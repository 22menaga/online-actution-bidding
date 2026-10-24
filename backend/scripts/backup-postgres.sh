#!/bin/sh
set -eu

: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

for setting in BACKUP_INTERVAL_SECONDS BACKUP_RETENTION_DAYS; do
    eval "value=\${$setting}"
    case "$value" in
        ''|*[!0-9]*) echo "$setting must be a positive integer." >&2; exit 2 ;;
    esac
    if [ "$value" -le 0 ]; then
        echo "$setting must be a positive integer." >&2
        exit 2
    fi
done

export PGHOST="$POSTGRES_HOST"
export PGPORT="${POSTGRES_PORT:-5432}"
export PGUSER="$POSTGRES_USER"
export PGPASSWORD="$POSTGRES_PASSWORD"
export PGDATABASE=postgres

run_backup() {
    timestamp="$(date -u '+%Y%m%dT%H%M%SZ')"
    backup_file="/backups/${POSTGRES_DB}_${timestamp}_$$.dump"
    temporary_file="${backup_file}.tmp"
    restore_database=""

    cleanup_backup() {
        if [ -f "$temporary_file" ]; then
            rm -f "$temporary_file"
        fi
        if [ -n "$restore_database" ]; then
            dropdb --if-exists --force "$restore_database" || \
                echo "Could not remove temporary restore-check database: $restore_database" >&2
        fi
    }
    trap cleanup_backup EXIT HUP INT TERM

    echo "Creating PostgreSQL backup: $(basename "$backup_file")"
    pg_dump \
        --format=custom \
        --no-owner \
        --no-acl \
        --file="$temporary_file" \
        "$POSTGRES_DB"
    mv "$temporary_file" "$backup_file"
    restore_database="auction_restore_check_${timestamp}_$$"

    echo "Checking backup by restoring into a temporary database."
    createdb --template=template0 --owner="$POSTGRES_USER" "$restore_database"
    PGDATABASE="$restore_database" pg_restore \
        --exit-on-error \
        --no-owner \
        --no-acl \
        --dbname="$restore_database" \
        "$backup_file"
    dropdb --if-exists --force "$restore_database"
    restore_database=""
    trap - EXIT HUP INT TERM

    if [ -n "${S3_BACKUP_BUCKET:-}" ]; then
        s3_key="${S3_BACKUP_PREFIX:-auction-postgres}/$(basename "$backup_file")"
        echo "Uploading verified backup to the configured S3 bucket."
        aws s3 cp "$backup_file" "s3://${S3_BACKUP_BUCKET}/${s3_key}" \
            --region "${AWS_REGION:-us-east-1}" \
            --sse AES256 \
            --only-show-errors
        encryption="$(aws s3api head-object \
            --bucket "$S3_BACKUP_BUCKET" \
            --key "$s3_key" \
            --region "${AWS_REGION:-us-east-1}" \
            --query ServerSideEncryption \
            --output text)"
        if [ "$encryption" != "AES256" ]; then
            echo "S3 backup encryption verification failed." >&2
            return 1
        fi
        echo "S3 upload verified with AES256 server-side encryption."
    fi

    find /backups -type f -name "${POSTGRES_DB}_*.dump" \
        -mtime "+${BACKUP_RETENTION_DAYS}" -delete
    echo "Backup and restore check completed successfully."
}

while :; do
    run_backup
    if [ "${BACKUP_ONCE:-0}" = "1" ]; then
        exit 0
    fi
    sleep "$BACKUP_INTERVAL_SECONDS"
done
