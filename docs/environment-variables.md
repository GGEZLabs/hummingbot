# Environment Variables

## Hummingbot CLI (docker-compose.yml)

Set under the `environment:` section of the CLI service.

| Variable | Example | Description |
| :---- | :---- | :---- |
| `CONFIG_PASSWORD` | `<your_password>` | Password used to decrypt the Hummingbot keyfile and unlock the bot on startup. |
| `CONFIG_FILE_NAME` | `random_transactions.py` | The script file to auto-start when the container launches. |
| `SCRIPT_CONFIG` | `conf_random_transactions_10.yml` | The config file passed to the auto-started script. |
| `HEADLESS_MODE` | `true` | Run Hummingbot without the interactive CLI UI (required for Docker/automated deployments). |

## Hummingbot Backend API (.env)

| Variable | Example | Description |
| :---- | :---- | :---- |
| `USERNAME` | `<your_username>` | Dashboard login username, also used by the backend API auth. |
| `PASSWORD` | `<your_password>` | Dashboard login password. |
| `DEBUG_MODE` | `false` | Enable verbose debug logging in the backend API. |
| `CONFIG_PASSWORD` | `<your_password>` | Password used to unlock Hummingbot CLI instances spawned by the backend. |
| `BROKER_HOST` | `localhost` | Hostname of the MQTT broker used for real-time bot communication. |
| `BROKER_PORT` | `1883` | Port of the MQTT broker. |
| `BROKER_USERNAME` | `<broker_user>` | MQTT broker authentication username. |
| `BROKER_PASSWORD` | `<broker_password>` | MQTT broker authentication password. |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` | Full async connection string for the backend API PostgreSQL database. |
| `DATABASE_USED_SCHEMA` | `public` | PostgreSQL schema used by the backend API tables. |
| `MARKET_DATA_CLEANUP_INTERVAL` | `300` | How often (in seconds) stale market data records are purged from memory. |
| `MARKET_DATA_FEED_TIMEOUT` | `600` | Seconds before an inactive market data feed is considered timed out. |
| `AWS_API_KEY` | *(optional)* | AWS access key ID, required only if using S3 for storage. |
| `AWS_SECRET_KEY` | *(optional)* | AWS secret access key, paired with `AWS_API_KEY`. |
| `AWS_S3_DEFAULT_BUCKET_NAME` | *(optional)* | S3 bucket name for file storage (optional feature). |
| `LOGFIRE_ENVIRONMENT` | `prod` | Logfire observability environment tag (`prod`, `dev`, etc.). |
| `BANNED_TOKENS` | `["NAV","ARS",...]` | JSON list of token symbols excluded from rate oracle and market data collection. |
| `BOTS_PATH` | `/shared-efs` | Host path where bot instance folders (conf, logs, scripts) are stored. Use `/shared-efs/bots/` on AWS, local path on other servers. |

## Hummingbot Dashboard (docker-compose.yml)

Set under the `environment:` section of the dashboard service.

| Variable | Example | Description |
| :---- | :---- | :---- |
| `AUTH_SYSTEM_ENABLED` | `True` | Enable login authentication for the dashboard UI. |
| `BACKEND_API_HOST` | `hummingbot-api` | Hostname of the backend API service (Docker service name or IP). |
| `BACKEND_API_PORT` | `8000` | Port the backend API listens on. |
| `BACKEND_API_USERNAME` | `${USERNAME}` | Username the dashboard uses to authenticate with the backend API. |
| `BACKEND_API_PASSWORD` | `${PASSWORD}` | Password the dashboard uses to authenticate with the backend API. |
| `HASURA_GRAPHQL_URL` | `<HASURA_GRAPHQL_URL>` | Hasura GraphQL endpoint for market data queries (use demo or live URL accordingly). |
