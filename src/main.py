import os
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import psycopg
import requests
from loguru import logger

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYYMMDD-HHmmss}</green> | <level>{message}</level>",
    colorize=True
)


def get_assets():
    host = os.getenv("DB_HOSTNAME", "immich_postgres")
    port = os.getenv("DB_PORT", "5432")
    db = os.getenv("DB_DATABASE_NAME", "immich")
    user = os.getenv("DB_USERNAME", "postgres")
    pw = os.getenv("DB_PASSWORD", "postgres")
    
    conn_str = f"host={host} port={port} dbname={db} user={user} password={pw}"
    
    path_patterns = os.getenv("IMMICH_UPLOAD_PATH", "/usr/src/app/upload/library/%")
    patterns = [p.strip() for p in path_patterns.split(',')]
    
    query = 'SELECT id, "originalPath" FROM asset WHERE "originalPath" LIKE %s AND "deletedAt" IS NULL'
    
    all_assets = []
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                for pattern in patterns:
                    cur.execute(query, (pattern,))
                    all_assets.extend(cur.fetchall())
        return all_assets
    except psycopg.OperationalError as e:
        logger.error(f"DB Error: {e}")
        logger.error(
            f"Failed to connect to database at host='{host}', port='{port}', "
            f"dbname='{db}', user='{user}'. "
            f"Make sure DB_HOSTNAME is set to the correct hostname of the PostgreSQL "
            f"container (e.g. the Docker service name). "
            f"The default value 'localhost' does not work in Docker, as it refers to "
            f"the container itself, not the database container."
        )
        return []
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return []

def delete_assets(asset_ids):
    api_url = os.getenv("IMMICH_URL")
    api_key = os.getenv("IMMICH_API_KEY") 
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": api_key 
    }
    
    payload = {"ids": asset_ids}
    
    response = requests.delete(f"{api_url}/api/assets", json=payload, headers=headers)
    
    if response.status_code in [200, 201, 204]:
        logger.info(f"Success: {len(asset_ids)} assets trashed.")
    else:
        logger.error(f"API Error ({response.status_code}): {response.text}")

def delete_offline_assets():
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    max_ratio = float(os.getenv("MAX_MISSING_RATIO", "0.1"))
    
    logger.info("Starting scheduled scan...")
    assets = get_assets()
    if not assets:
        logger.warning("No assets found in database.")
        return
        
    missing = [(aid, p) for aid, p in assets if not os.path.exists(p)]
    
        
    ratio = len(missing) / len(assets)
    logger.info(f"Stats: {len(missing)} missing / {len(assets)} total (Ratio: {ratio:.2%})")
    
    if not missing:
        logger.info("No missing assets found.")
        return

    if ratio > max_ratio:
        logger.warning(f"ALERT: Ratio {ratio:.2%} too high. Aborting.")
        return

    if dry_run:
        logger.info(f"[DRY RUN] Would delete {len(missing)} assets.")
        for _, p in missing: logger.debug(f"Preview: {p}")
    else:
        ids_to_delete = [str(aid) for aid, _ in missing]
        logger.info(f"Proceeding to delete {len(missing)} assets via API...")
        delete_assets(ids_to_delete)

if __name__ == "__main__":
    logger.info("=== Immich Offline Remover ===")
    cron_expr = os.getenv("CRON_EXPRESSION", "0 3 * * *")
    
    scheduler = BlockingScheduler()
    scheduler.add_job(delete_offline_assets, CronTrigger.from_crontab(cron_expr))
    
    logger.info(f"Immich Offline Remover started. Cron: {cron_expr}")
    
    # Signal handling to stop docker immediately (no 10s timeout)
    signal.signal(signal.SIGTERM, lambda sn, frame: scheduler.shutdown(wait=False))
    signal.signal(signal.SIGINT, lambda sn, frame: scheduler.shutdown(wait=False))
    
    run_at_first_startup = os.getenv("RUN_AT_FIRST_STARTUP", "false").lower() == "true"
    if run_at_first_startup:
        logger.info("Running initial scan at startup...")
        delete_offline_assets()
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Service stopping...")