#!/bin/bash

set -e

# Pick up settings for multi-site backup
source ~/.wp-backup

KEEP_BACKUPS=${NUM_TO_KEEP:-8}

for site in $SITES; do
    echo "Processing site $site"
    BACKUP_PARENT=~/backup/$HOST_ID/$site
    if [ -d "$BACKUP_PARENT" ]; then
        echo "Purge old local backup copies - keep last ${KEEP_BACKUPS}"
        ( cd $BACKUP_PARENT && ls -t1 | tail -n +$KEEP_BACKUPS | xargs rm -fr )
    fi
    export BACKUP_DIR=$BACKUP_PARENT/backup-$(date "+%Y%m%d%H%M%S")
    mkdir -p $BACKUP_DIR
    sudo $SCRIPT_DIR/backup.py $site /var/www/$site/public_html -o $BACKUP_DIR
    sudo chown -R $USER $BACKUP_DIR
    echo "Uploading to s3 (under $S3_ROOT/$HOST_ID/$site/)"
    aws s3 cp --quiet --recursive $BACKUP_DIR $S3_ROOT/$HOST_ID/$site/
done

