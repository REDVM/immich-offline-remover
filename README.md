# Description

This tool helps to remove offline assets from Immich.

Assets are uploaded in Immich in the internal path `/usr/src/app/upload/library/...`. Sometimes, I like to move some of these assets to specific folder in my external library. But these assets are still in the database, their thumbnails/encoded version are still there, therefore they does not disappear from the webapp.

This tool browses the database for assets beginning by `/usr/src/app/upload/library/`, tests if the file still exists, if it's not the case, it calls Immich API to put it in the trash. Files in the Immich trash can be manually removed from the webapp or it will be automatically after a period (30 days by default).


If immich changes the API endpoint specification, this tool might not work anymore. This tool is not officially supported by Immich and is provided as-is.

Tested Immich Version: `v2.3.1`. After manually emptying the trash, the thumbs (and encoded video if any) are correctly removed, even if the original asset is already deleted.



# Usage

Open your `docker-compose.yml` with your immich stack and add the following service:

```yaml
immich-offline-remover:
    image: redvm/immich-offline-remover:latest
    container_name: immich_offline_remover
    hostname: immich_offline_remover
    env_file:
        - .env         # We reuse the same .env as immich stack!
    environment:
        IMMICH_URL: http://immich-server:2283
        IMMICH_API_KEY: <YOUR-API-KEY>
        CRON_EXPRESSION: "0 3 * * *"
        DRY_RUN: "false"
        RUN_AT_FIRST_STARTUP: "true"
        MAX_MISSING_RATIO: "0.1"
    volumes:
        - ${UPLOAD_LOCATION}:/usr/src/app/upload:ro
    depends_on:
      - database
    restart: unless-stopped
```

In this example we use the same `.env` as immich. If you don't use it in your stack, please set `DB_HOSTNAME`, `DB_DATABASE_NAME`, `DB_USERNAME`, `DB_PASSWORD` to your own values.


Specific env var used by the container:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| IMMICH_URL | *None* | URL of the Immich instance (e.g., "http://immich-server:2283") |
| IMMICH_API_KEY | *None* | API key for Immich authentication |
| CRON_EXPRESSION | `0 3 * * *` | Cron expression for scheduled runs (e.g., `0 3 * * *` for 3 AM daily) |
| DRY_RUN | `true` | If set to `true`, no changes will be made to Immich |
| MAX_MISSING_RATIO | `0.1` | Maximum ratio of missing files allowed (e.g., `0.1` for 10%). If the ratio is exceeded, the script will exit without making any changes. It serves as a safeguard. |
| RUN_AT_FIRST_STARTUP | `false` | If set to `true`, the script will run once at startup (and still follow the CRON_EXPRESSION for the next runs) |
| IMMICH_UPLOAD_PATH | `/usr/src/app/upload/library/%` | SQL pattern (comma separated) to match asset paths in DB. |
| DB_HOSTNAME | `immich_postgres` | Hostname of the container running the Immich DB. In Docker, you must set this to the database service name or container name (e.g. `database`, `immich_postgres`). |
| DB_PORT | `5432` | Port of the database |
| DB_DATABASE_NAME | `immich` | Name of the database |
| DB_USERNAME | `postgres` | Database user |
| DB_PASSWORD | `postgres` | Database password |


Note: This tool assumes that there is a database named `immich`, with a table named `asset` with 3 columns `id`,  `originalPath`, and `deletedAt`.
It assumes that `originalPath` contains the full path to the asset on the filesystem, and that `deletedAt` is null for active assets (non-null for trashed assets). 

It assumes that we can send a `DELETE` request to the `/api/assets` endpoint of immich-server with a list of assets ids to trash them.
