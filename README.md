# Pytheus Watchdog

Unified system and platform monitoring web app with AI-powered alert triage (Phase 3).

Built and supported by **Pytheus**. Deployed to `vps.pytheus.com` via Docker.

## Features (Phase 1 MVP)

- **HTTP/HTTPS Endpoint Monitoring** - Monitor uptime, response time, status codes, and content matching
- **Smart Alert Retry Logic** - Automatically retries failed checks 3 times with exponential backoff to filter transient issues
- **Dead Man's Switch** - Webhook endpoints for cron jobs and workflows to ping on success
- **Multi-Channel Notifications** - Slack and Telegram notifications with severity-based formatting
- **Real-time Dashboard** - Clean, minimal web interface showing service status, uptime, and incidents
- **Incident Management** - Automatic incident creation, tracking, and resolution
- **Uptime Tracking** - Calculate and display uptime percentages over 24h, 7d, and 30d periods

## Architecture

### Tech Stack

- **Backend**: Python + FastAPI
- **Frontend**: React + Tailwind CSS + Vite
- **Database**: SQLite (with async support via aiosqlite)
- **Scheduler**: APScheduler (for running periodic checks)
- **Deployment**: Docker + Docker Compose
- **Reverse Proxy**: Nginx with Let's Encrypt SSL

### Container Design

Fully containerized with:
- Resource limits (0.5 CPU, 512MB RAM)
- Non-root user (UID 1000)
- Named volumes for data persistence
- Health checks on all services
- Isolated Docker network
- Automatic restart policies

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Domain name pointed to your VPS (e.g., `watchdog.pytheus.com`)
- Slack webhook URL (optional but recommended)
- Telegram bot token and chat ID (optional but recommended)

### 1. Clone and Configure

```bash
git clone <repository-url>
cd pytheus-watchdog

# Copy and edit environment variables
cp .env.example .env
nano .env  # Fill in your credentials
```

### 2. Configure Monitoring Targets

Edit `config/watchdog.yaml` to add your services:

```yaml
targets:
  - name: "My Service"
    type: http
    url: "https://myservice.com/health"
    interval: 60  # seconds
    severity: critical
    alerts: [slack, telegram]
    timeout: 10
```

### 3. Build and Deploy

```bash
# Build the Docker image
docker compose build

# Start the container
docker compose up -d

# Check logs
docker compose logs -f

# Verify health
curl http://localhost:8000/api/health
```

### 4. Configure Nginx Reverse Proxy

```bash
# Copy Nginx config
sudo cp nginx/watchdog.conf /etc/nginx/sites-available/watchdog.conf

# Create symlink
sudo ln -s /etc/nginx/sites-available/watchdog.conf /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### 5. Set up SSL with Let's Encrypt

```bash
sudo certbot --nginx -d watchdog.pytheus.com
```

### 6. Access Dashboard

Visit `https://watchdog.pytheus.com` to see your monitoring dashboard!

## Setting Up Telegram Notifications

### Step 1: Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Choose a name (e.g., "Pytheus Watchdog")
4. Choose a username (e.g., "pytheus_watchdog_bot")
5. Copy the **bot token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Chat ID

**Option A: Personal Chat**
1. Message your bot with any text (e.g., "/start")
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Look for `"chat":{"id":123456789` - that's your chat ID

**Option B: Group Chat**
1. Create a group and add your bot to it
2. Make the bot an admin (optional but recommended)
3. Send a message in the group
4. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
5. Look for the chat ID (will be negative for groups, e.g., `-123456789`)

### Step 3: Add to .env

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789  # or -123456789 for groups
```

### Step 4: Test Notifications

Restart the container and trigger a test alert by temporarily making a monitored service unreachable.

## Setting Up Slack Notifications

1. Go to [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)
2. Create a new webhook for your workspace
3. Choose the channel (e.g., `#monitoring`)
4. Copy the webhook URL
5. Add to `.env`:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Dead Man's Switch Setup

Dead man's switches monitor cron jobs and workflows by expecting regular "pings". If a ping is missed, you'll be alerted.

### Getting Webhook URLs

Visit the dashboard and navigate to the Dead Man's Switches section, or use the API:

```bash
curl https://watchdog.pytheus.com/api/deadman/YOUR_SWITCH_NAME/webhook-url
```

### Using in Cron Jobs

```bash
# Example cron job that pings on success
0 * * * * /path/to/script.sh && curl -X POST https://watchdog.pytheus.com/api/ping/YOUR_TOKEN
```

### Using in n8n Workflows

Add an HTTP Request node at the end of your workflow:
- Method: POST
- URL: `https://watchdog.pytheus.com/api/ping/YOUR_TOKEN`

### Using in Python Scripts

```python
import requests

def my_task():
    # Your task logic here
    pass

try:
    my_task()
    # Ping on success
    requests.post("https://watchdog.pytheus.com/api/ping/YOUR_TOKEN")
except Exception as e:
    print(f"Task failed: {e}")
    # Don't ping - watchdog will alert after expected_interval
```

## Monitoring Configuration

### Target Types

**HTTP Checks**
```yaml
- name: "My API"
  type: http
  url: "https://api.example.com/health"
  interval: 60
  timeout: 10
  expected_status: 200
  content_match: "ok"  # Optional
  severity: critical
  alerts: [slack, telegram]
```

### Severity Levels

- `critical` - Production systems, customer-facing services
- `warning` - Non-critical services, degraded performance
- `info` - Informational notifications

### Notification Channels

Configure in `config/watchdog.yaml`:
```yaml
notifications:
  slack:
    enabled: true
    webhook_url: ${SLACK_WEBHOOK_URL}
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}
```

## Data Management

### Backup Data Volume

```bash
# Stop container
docker compose down

# Backup SQLite database
docker run --rm -v pytheus-watchdog-data:/data -v $(pwd):/backup alpine tar czf /backup/watchdog-backup-$(date +%Y%m%d).tar.gz -C /data .

# Restart container
docker compose up -d
```

### Restore from Backup

```bash
# Stop container
docker compose down

# Remove old volume
docker volume rm pytheus-watchdog-data

# Create new volume
docker volume create pytheus-watchdog-data

# Restore data
docker run --rm -v pytheus-watchdog-data:/data -v $(pwd):/backup alpine tar xzf /backup/watchdog-backup-YYYYMMDD.tar.gz -C /data

# Restart container
docker compose up -d
```

### Data Retention

- Check results: 90 days (configurable in Phase 4)
- Incidents: Indefinite
- Database is automatically managed by SQLAlchemy

## API Endpoints

### Dashboard
- `GET /api/dashboard` - Full dashboard data

### Targets
- `GET /api/targets/{name}/history?hours=24` - Check history for a target

### Incidents
- `GET /api/incidents?status=open` - List incidents
- `POST /api/incidents/{id}/acknowledge` - Acknowledge incident

### Dead Man's Switch
- `POST /api/ping/{token}` - Receive ping (called by your services)
- `GET /api/deadman/{name}/webhook-url` - Get webhook URL

### Health
- `GET /api/health` - Health check endpoint

## Resource Usage

Expected resource consumption:
- **CPU**: 0.25-0.5 cores (limited to 0.5)
- **Memory**: 256-512MB (limited to 512MB)
- **Disk**: ~100MB + SQLite database growth (~1MB per 10,000 checks)
- **Network**: Minimal (only outbound checks and notifications)

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs

# Check if port 8000 is available
sudo netstat -tlnp | grep 8000

# Verify .env file exists and has correct values
cat .env
```

### Notifications not working

```bash
# Check Slack webhook
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test from Pytheus Watchdog"}' \
  YOUR_SLACK_WEBHOOK_URL

# Check Telegram bot
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage?chat_id=YOUR_CHAT_ID&text=Test"
```

### Monitoring checks failing

```bash
# Enter container
docker compose exec watchdog-app bash

# Test URL from inside container
curl -v https://your-service.com

# Check DNS resolution
nslookup your-service.com
```

### Database issues

```bash
# Access SQLite database
docker compose exec watchdog-app sqlite3 /app/data/watchdog.db

# List tables
.tables

# Check recent checks
SELECT * FROM check_results ORDER BY checked_at DESC LIMIT 10;

# Exit
.quit
```

## Updating

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose down
docker compose build
docker compose up -d

# Check logs
docker compose logs -f
```

## Complete Teardown

```bash
# Stop and remove containers
docker compose down

# Remove volumes (WARNING: deletes all data)
docker volume rm pytheus-watchdog-data

# Remove network
docker network rm pytheus-watchdog-network

# Remove images
docker rmi $(docker images | grep pytheus-watchdog | awk '{print $3}')
```

## Roadmap

### Phase 2 - Platform Awareness (Coming Soon)
- Status page scraping for third-party platforms
- Correlation logic (cross-reference with platform status)
- Server resource monitoring

### Phase 3 - AI Triage
- LLM integration (Claude/OpenAI)
- Smart alert summarization
- Root cause hints

### Phase 4 - Polish
- Configuration UI
- Public status page
- Email notifications
- SMS via Twilio
- Advanced analytics

## Support

Built and maintained by **Pytheus**.

For issues, questions, or feature requests, contact the development team.

## License

Proprietary - Internal use only.
