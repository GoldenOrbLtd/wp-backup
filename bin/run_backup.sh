#!/bin/bash

set -e

# Pick up settings for multi-site backup
source ~/.wp-backup

for site in $SITES; do
    echo "Processing site $site"
    export BACKUP_DIR=~/backup/$HOST_ID/$site/backup-$(date "+%Y%m%d%H%M%S")
    mkdir -p $BACKUP_DIR
    sudo $SCRIPT_DIR/backup.py $site /var/www/$site/public_html -o $BACKUP_DIR
    sudo chown -R $USER $BACKUP_DIR
    echo "Uploading to s3 (under $S3_ROOT/$HOST_ID/$site/)"
    aws s3 cp --quiet --recursive $BACKUP_DIR $S3_ROOT/$HOST_ID/$site/
done

