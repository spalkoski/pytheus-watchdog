# Pytheus Watchdog

Unified system and platform monitoring web app with AI-powered alert triage.

Built and supported by **Pytheus**. Deployed to `vps.pytheus.com` via Docker.

## Features

- **HTTP/HTTPS Endpoint Monitoring** - Monitor uptime, response time, status codes, and content matching
- **Ping/ICMP Monitoring** - Monitor network connectivity to hosts (e.g., Tailscale gateways)
- **Status Page Parsing** - Scrape third-party status pages (Replit, Jedox, etc.) to detect platform issues
- **AI-Powered Triage** - Claude AI confirms platform issues before alerting, reducing false positives
- **Smart Alert Retry Logic** - Retries failed checks 3 times with exponential backoff
- **Dead Man's Switch** - Webhook endpoints for cron jobs and workflows to ping on success
- **Daily Status Digest** - Automated morning report at 7am Pacific with full system status
- **Multi-Channel Notifications** - Slack and Telegram notifications with severity-based formatting
- **Real-time Dashboard** - Clean web interface showing service status, uptime, and incidents
- **Incident Management** - Automatic incident creation, tracking, and resolution
- **Uptime Tracking** - Calculate and display uptime percentages over 24h, 7d, and 30d periods

## Architecture

### Tech Stack

- **Backend**: Python + FastAPI
- **Frontend**: React + Tailwind CSS + Vite
- **Database**: SQLite (with async support via aiosqlite)
- **Scheduler**: APScheduler (interval and cron triggers)
- **AI**: Anthropic Claude API for alert triage
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
- Telegram bot token and chat ID
- Slack webhook URL (optional)
- Anthropic API key (for AI triage)

### 1. Clone and Configure

```bash
git clone https://github.com/spalkoski/pytheus-watchdog.git
cd pytheus-watchdog

# Copy and edit environment variables
cp .env.example .env
nano .env  # Fill in your credentials
```

### 2. Configure Monitoring Targets

Edit `config/watchdog.yaml` to add your services:

```yaml
targets:
  # HTTP endpoint monitoring
  - name: "My Service"
    type: http
    url: "https://myservice.com/health"
    interval: 60  # seconds
    severity: critical
    alerts: [slack, telegram]
    timeout: 10

  # Ping/ICMP monitoring (e.g., Tailscale networks)
  - name: "Tailscale Gateway"
    type: ping
    host: "10.1.1.1"
    interval: 60
    severity: critical
    alerts: [slack, telegram]
    timeout: 5

  # Status page monitoring (auto-detected by name/URL)
  - name: "Replit Status"
    type: http
    url: "https://status.replit.com"
    interval: 300
    severity: warning
    alerts: [slack, telegram]
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
curl http://localhost:8100/api/health
```

### 4. Configure Nginx Reverse Proxy

```bash
# Copy Nginx config
sudo cp nginx/watchdog.conf /etc/nginx/sites-available/watchdog.conf
sudo ln -s /etc/nginx/sites-available/watchdog.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Set up SSL with Let's Encrypt

```bash
sudo certbot --nginx -d watchdog.pytheus.com
```

### 6. Access Dashboard

Visit `https://watchdog.pytheus.com` to see your monitoring dashboard!

## Notification Setup

### Telegram

1. Message [@BotFather](https://t.me/BotFather) and send `/newbot`
2. Copy the bot token
3. Message your bot, then get your chat ID:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
4. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```

### Slack

1. Create an [Incoming Webhook](https://api.slack.com/messaging/webhooks)
2. Add to `.env`:
   ```
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```

### Test Notifications

```bash
# Test Telegram
curl -X POST http://localhost:8100/api/test-notification/telegram

# Test Slack
curl -X POST http://localhost:8100/api/test-notification/slack

# Test daily digest
curl -X POST http://localhost:8100/api/test-digest
```

## Daily Status Digest

Every day at **7:00 AM Pacific**, you'll receive a status report including:
- Overall system health (all up, issues detected, degradation)
- Status of each monitored service with 24h uptime percentage
- Dead man's switch statuses
- Summary counts (up/down/degraded)

This ensures you're reminded of any long-standing issues even if no new alerts fire.

## AI-Powered Triage

When a status page shows potential issues, the AI triage system:
1. Parses the status page HTML for incident indicators
2. Sends the content to Claude for analysis
3. Determines if the issue is real or a false positive
4. Only creates an incident if confirmed
5. Provides a summary explaining the AI's reasoning

This dramatically reduces false positive alerts from status pages.

## Monitoring Types

### HTTP Checks
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

### Ping/ICMP Checks
```yaml
- name: "Network Gateway"
  type: ping
  host: "10.1.1.1"
  interval: 60
  timeout: 5
  severity: critical
  alerts: [slack, telegram]
```

### Dead Man's Switches
```yaml
deadman_switches:
  - name: "Daily Backup"
    expected_interval: 86400  # 24 hours
    severity: critical
    alerts: [slack, telegram]
```

## Dead Man's Switch Usage

### Get Webhook URL
```bash
curl https://watchdog.pytheus.com/api/deadman/YOUR_SWITCH_NAME/webhook-url
```

### In Cron Jobs
```bash
0 * * * * /path/to/script.sh && curl -X POST https://watchdog.pytheus.com/api/ping/YOUR_TOKEN
```

### In n8n Workflows
Add an HTTP Request node at the end:
- Method: POST
- URL: `https://watchdog.pytheus.com/api/ping/YOUR_TOKEN`

### In Python
```python
import requests

try:
    my_task()
    requests.post("https://watchdog.pytheus.com/api/ping/YOUR_TOKEN")
except Exception as e:
    pass  # Don't ping - watchdog will alert
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/dashboard` | GET | Full dashboard data |
| `/api/targets/{name}/history` | GET | Check history for a target |
| `/api/incidents` | GET | List incidents |
| `/api/incidents/{id}/acknowledge` | POST | Acknowledge incident |
| `/api/ping/{token}` | POST | Dead man's switch ping |
| `/api/deadman/{name}/webhook-url` | GET | Get webhook URL |
| `/api/test-notification/{channel}` | POST | Test notification (telegram/slack) |
| `/api/test-digest` | POST | Send test daily digest |

## Data Management

### Backup
```bash
docker compose down
docker run --rm -v pytheus-watchdog-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/watchdog-backup-$(date +%Y%m%d).tar.gz -C /data .
docker compose up -d
```

### Restore
```bash
docker compose down
docker volume rm pytheus-watchdog-data
docker volume create pytheus-watchdog-data
docker run --rm -v pytheus-watchdog-data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/watchdog-backup-YYYYMMDD.tar.gz -C /data
docker compose up -d
```

## Troubleshooting

### Check Logs
```bash
docker compose logs -f
docker compose logs --tail 50 | grep -i error
```

### Test from Inside Container
```bash
docker compose exec pytheus-watchdog bash
curl -v https://your-service.com
ping 10.1.1.1
```

### Access Database
```bash
docker compose exec pytheus-watchdog sqlite3 /app/data/watchdog.db
.tables
SELECT * FROM check_results ORDER BY checked_at DESC LIMIT 10;
.quit
```

## Updating

```bash
git pull
docker compose build
docker compose up -d
```

## Resource Usage

- **CPU**: 0.25-0.5 cores (limited to 0.5)
- **Memory**: 256-512MB (limited to 512MB)
- **Disk**: ~100MB + database growth

## Roadmap

### Phase 4 - Polish (Planned)
- Configuration UI
- Public status page
- Email notifications
- SMS via Twilio
- Advanced analytics
- Data retention policies

## Support

Built and maintained by **Pytheus**.

GitHub: https://github.com/spalkoski/pytheus-watchdog

## License

Proprietary - Internal use only.
