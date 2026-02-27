# Pytheus Watchdog — Full Specification

## Context & Problem

I run multiple self-hosted services on my VPS (vps.pytheus.com) alongside critical third-party hosted platforms (Replit, Jedox, NocoDB, n8n, etc.). I recently lost 2+ hours debugging what turned out to be a Replit platform outage — not my code. I need a single-pane-of-glass monitoring system that tracks uptime, process health, and platform status, with an AI triage layer that evaluates alerts before notifying me so I'm not chasing false positives.

This project is implemented and supported by **Pytheus**.

## Deployment Target

- **Host:** vps.pytheus.com (Ubuntu/Debian VPS on Hostinger)
- **Domain:** Subdomain like `watchdog.pytheus.com` or `monitor.pytheus.com`
- **Resources:** Shared VPS running other production services — this app **must not interfere** with existing workloads
- **⚠️ CRITICAL: Full Docker isolation is mandatory.** The VPS already runs other services. This app must be fully containerized via Docker Compose so it cannot break, conflict with, or consume resources from anything else on the server. No host-level package installations. No shared databases. Everything self-contained in containers with resource limits defined.

## Core Architecture

### Tech Stack Preferences
- **Backend:** Node.js (Express or Fastify) or Python (FastAPI) — dealer's choice based on what's most maintainable
- **Frontend:** Clean, minimal dashboard — React or even a well-built server-rendered template is fine. No heavy frameworks needed.
- **Database:** SQLite for simplicity (or Postgres in its own container if there's a strong reason). Store check history, incident logs, alert records.
- **Reverse proxy:** Will sit behind Nginx (already on the VPS) — provide the Nginx config snippet needed to proxy to the container
- **Containerization:** Docker Compose **required** — all services (app, database, any workers) must be in containers with:
  - Defined CPU and memory limits
  - Named volumes for persistent data (not bind mounts to host system directories)
  - An isolated Docker network
  - Restart policies
  - Health checks on each container

### Docker Compose Requirements
```yaml
# Example structure expected:
services:
  watchdog-app:
    build: .
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    restart: unless-stopped
    networks:
      - watchdog-net
    volumes:
      - watchdog-data:/app/data

  # If using a separate DB container:
  watchdog-db:
    image: postgres:16-alpine  # or skip if using SQLite
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M
    restart: unless-stopped
    networks:
      - watchdog-net
    volumes:
      - watchdog-db-data:/var/lib/postgresql/data

networks:
  watchdog-net:
    driver: bridge

volumes:
  watchdog-data:
  watchdog-db-data:
```

---

## Monitoring Capabilities

### 1. HTTP/HTTPS Endpoint Monitoring
- Configurable list of URLs to check at defined intervals (e.g., every 1–5 minutes)
- Track: response code, response time, SSL cert expiry, content match (optional keyword in response body)
- Targets include:
  - My self-hosted apps (n8n, NocoDB, internal APIs)
  - Third-party platform health endpoints and status pages

### 2. Third-Party Platform Status Monitoring
Scrape or poll status pages for platforms I depend on:
- **Replit** — status.replit.com
- **Jedox** — whatever their status mechanism is
- **Hostinger** — statuspage or API
- **OpenAI API** — status.openai.com
- **Anthropic API** — status page
- **GitHub** — githubstatus.com
- **Slack** — status.slack.com
- Make it easy to add new platforms via config (URL + CSS selector or JSON path for status parsing)

### 3. Process / Cron Job Monitoring (Dead Man's Switch)
- Provide unique webhook URLs that my cron jobs and n8n workflows ping on successful completion
- If a ping isn't received within the expected window, flag it as a failure
- Use case: My n8n workflows that run research automations, data syncs, etc. should each ping Watchdog on success

### 4. Server Resource Monitoring (Local VPS)
- CPU, memory, disk usage on the VPS itself
- Since the app is containerized, use one of:
  - A lightweight sidecar container that mounts `/proc` and `/sys` read-only to report host metrics
  - Or an API endpoint on the host that the container calls (provide the small script to install)
- Alert on thresholds (e.g., disk > 85%, memory > 90%)
- **No host-level agent installations** — keep it container-friendly

### 5. Port / TCP Checks
- Verify that specific ports are open and responding (e.g., Postgres on 5432, n8n on 5678)

---

## AI Triage Agent Layer

This is the key differentiator. **Don't just fire raw alerts — run them through an evaluation step first.**

### Triage Logic
- When a check fails, don't immediately notify. Instead:
  1. **Retry** — Re-check 2–3 times with short delays to filter transient blips
  2. **Correlate** — Is the platform's status page also reporting issues? If Replit's status page shows degraded, the alert context changes from "your app is broken" to "platform issue — not your code"
  3. **Classify severity:**
     - 🔴 **Critical:** Self-hosted production system down (n8n, NocoDB, customer-facing APIs)
     - 🟡 **Warning:** Third-party platform degraded, non-critical service slow, resource threshold approaching
     - 🟢 **Info:** Transient blip recovered, platform status changed, scheduled maintenance detected
  4. **Deduplicate** — Don't send 50 alerts for the same ongoing incident. Group into incidents with updates.

### AI Summary (LLM Integration)
- On alert trigger, optionally call Claude API (or OpenAI as fallback) with:
  - The failing check details
  - Recent check history for that target
  - Platform status page data if relevant
  - Other correlated failures
- Ask the LLM to produce a brief assessment: "Is this likely my code, a platform issue, or a transient network blip? What should I check first?"
- Include this summary in the notification
- **Make LLM calls optional/configurable** — the system should work fine without them, just with rule-based triage

---

## Notification Channels
- **Slack** (primary) — Send to a dedicated `#monitoring` channel via webhook. Format alerts as rich Slack blocks with severity color, summary, affected service, and direct link to dashboard.
- **Telegram** (primary) — Send alerts via Telegram Bot API to a dedicated monitoring chat/group. Include severity emoji, service name, triage summary, and dashboard link. Support both private chats and group notifications.
- **Email** (secondary/backup) — For critical alerts
- **Optional:** SMS via Twilio for true emergencies (production customer-facing systems down for >10 min)
- Notification preferences should be configurable per-check and per-severity level

---

## Dashboard UI

### Main View
- Grid or list of all monitored targets with current status (up/down/degraded), response time, last checked
- Color-coded status indicators
- Uptime percentage over 24h / 7d / 30d per target

### Incident Timeline
- Chronological feed of incidents with: start time, duration, severity, AI triage summary, resolution status
- Ability to manually acknowledge/resolve incidents

### Status Page (Public-facing, optional)
- A simple `/status` page I could share with team members showing current system health
- No sensitive details, just service names and up/down status

### Configuration Panel
- Add/edit/remove monitoring targets via UI (not just config files)
- Set check intervals, alert thresholds, notification preferences
- Manage dead-man's-switch webhook endpoints

---

## Data & Retention
- Store raw check results for 90 days, then downsample to hourly summaries
- Store incidents indefinitely
- Provide basic data export (CSV or JSON) for check history

---

## Security
- Dashboard behind authentication (even basic auth to start, or better: a simple login with JWT)
- API endpoints for dead-man's-switch pings authenticated via unique tokens
- No sensitive credentials in code — use environment variables / `.env` file
- HTTPS via Let's Encrypt (handled at Nginx level on the host)
- Container runs as non-root user

---

## Configuration Format
Prefer a YAML or JSON config file for initial setup:

```yaml
targets:
  - name: "n8n"
    type: http
    url: "https://n8n.pytheus.com"
    interval: 60
    severity: critical
    alerts: [slack, telegram, email]

  - name: "NocoDB"
    type: http
    url: "https://nocodb.pytheus.com"
    interval: 60
    severity: critical
    alerts: [slack, telegram]

  - name: "Replit App - Solar API"
    type: http
    url: "https://my-app.replit.app/health"
    interval: 120
    severity: warning
    platform_status: "https://status.replit.com"
    alerts: [slack, telegram]

  - name: "Jedox"
    type: http
    url: "https://myinstance.jedox.cloud"
    interval: 300
    severity: warning
    platform_status: "jedox"
    alerts: [slack, telegram]

deadman_switches:
  - name: "n8n Research Workflow"
    expected_interval: 3600
    severity: warning
    alerts: [slack, telegram]

  - name: "Daily Data Sync"
    expected_interval: 86400
    severity: critical
    alerts: [slack, telegram, email]

platforms:
  - name: replit
    status_url: "https://status.replit.com"
    type: statuspage
  - name: openai
    status_url: "https://status.openai.com"
    type: statuspage
  - name: github
    status_url: "https://www.githubstatus.com"
    type: statuspage
  - name: anthropic
    status_url: "https://status.anthropic.com"
    type: statuspage
  - name: slack
    status_url: "https://status.slack.com"
    type: statuspage

notifications:
  slack:
    webhook_url: ${SLACK_WEBHOOK_URL}
    channel: "#monitoring"
  telegram:
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}
  email:
    smtp_host: ${SMTP_HOST}
    smtp_port: 587
    from: "watchdog@pytheus.com"
    to: ${ALERT_EMAIL}
  twilio:
    account_sid: ${TWILIO_ACCOUNT_SID}
    auth_token: ${TWILIO_AUTH_TOKEN}
    from_number: ${TWILIO_FROM_NUMBER}
    to_number: ${TWILIO_TO_NUMBER}

server:
  monitor_local: true
  disk_threshold: 85
  memory_threshold: 90
  cpu_threshold: 95
```

---

## Development Phases

### Phase 1 — Core Monitoring (MVP)
- HTTP endpoint checks with configurable intervals
- Simple dashboard showing status grid
- Slack and Telegram notifications on failure (with basic retry logic)
- SQLite storage
- Docker Compose deployment with resource limits
- Nginx reverse proxy config
- Dead man's switch webhooks

### Phase 2 — Platform Awareness
- Status page scraping/polling for third-party platforms
- Correlation logic (cross-reference failures with platform status)
- Incident grouping and deduplication
- Server resource monitoring (via container-safe approach)

### Phase 3 — AI Triage
- LLM integration for alert summarization and root cause hints
- Severity auto-classification with platform context
- Smart notification routing based on triage results
- Incident timeline with AI summaries

### Phase 4 — Polish
- Configuration UI (add/edit targets without touching config files)
- Public status page
- Uptime reporting and historical analytics
- Email and optional SMS notifications
- Data retention management

---

## Build vs. Extend Decision
I'm aware of Uptime Kuma, Gatus, Statping-ng, etc. Feel free to evaluate whether building on top of one of these (especially Uptime Kuma, which already has Docker support and a solid monitoring UI) makes more sense than building from scratch. If so, the work becomes:
- Deploy the base tool in Docker
- Build the AI triage layer as a sidecar container that intercepts alerts
- Add the platform status correlation logic
- Customize notifications with LLM summaries

**I'm open to either approach — tell me which you recommend and why before building.**

---

## Deployment Deliverables
The final output must include:
1. Complete `docker-compose.yml` with resource limits, health checks, restart policies
2. `Dockerfile(s)` for any custom images
3. `.env.example` with all required environment variables documented (including Telegram bot token and chat ID)
4. Nginx config snippet for reverse proxying from `watchdog.pytheus.com` to the container
5. A `README.md` with setup instructions, first-run configuration, Telegram bot setup guide, and how to add new monitoring targets
6. Backup/restore instructions for the data volume

---

## Success Criteria
1. I can see at a glance if any of my systems are down
2. If Replit goes down, I get a Slack message AND a Telegram message saying "Replit platform issue detected — not your code" within 5 minutes, instead of spending 2 hours debugging
3. My n8n workflows report health via dead man's switch, and I'm notified if one silently fails
4. Alert fatigue is minimized — I trust that when a notification arrives, it matters
5. The whole thing runs reliably in Docker on vps.pytheus.com without affecting other services
6. I can `docker compose down && docker compose up -d` with zero impact to anything else on the VPS
