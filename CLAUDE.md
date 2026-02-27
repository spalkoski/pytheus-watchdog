# Pytheus Watchdog

## Project Overview
Unified system and platform monitoring web app with AI-powered alert triage.
Built and supported by **Pytheus**. Deployed to **vps.pytheus.com** via Docker.

## Specification
The full product specification is in `docs/WATCHDOG_SPEC.md`. Read it before writing any code.

## Critical Constraints
- **Docker-only deployment.** Everything runs in containers via Docker Compose. No host-level package installations. No bind mounts to host system dirs. Named volumes only.
- **Resource limits required.** Every container must have CPU and memory limits defined. This VPS runs other production services.
- **Do not break the host.** This app coexists with n8n, NocoDB, Nginx, and other services on the same VPS. Zero host-level side effects.
- **Container runs as non-root user.**

## Build vs Extend Decision
Before writing ANY code, evaluate whether to build from scratch or extend an existing tool (Uptime Kuma, Gatus, etc.). Present your recommendation with reasoning. Wait for approval before proceeding.

## Development Phases
Work in phases. Do not skip ahead.
1. **Phase 1 — Core Monitoring (MVP):** HTTP checks, dashboard, Slack + Telegram notifications, SQLite, Docker Compose, Nginx config, dead man's switch webhooks
2. **Phase 2 — Platform Awareness:** Status page polling, correlation logic, incident grouping, server resource monitoring
3. **Phase 3 — AI Triage:** LLM integration, severity classification, smart routing, incident timeline
4. **Phase 4 — Polish:** Config UI, public status page, analytics, email/SMS, data retention

## Tech Preferences
- Backend: Node.js or Python (FastAPI) — recommend what's best
- Frontend: Minimal — React or server-rendered templates
- Database: SQLite preferred unless there's a strong reason for Postgres
- Config: YAML for initial setup, UI for ongoing management

## Deliverables Checklist
Every phase must include:
- [ ] Working `docker-compose.yml` with resource limits, health checks, restart policies
- [ ] `Dockerfile(s)` for custom images
- [ ] `.env.example` with all env vars documented
- [ ] Nginx config snippet for `watchdog.pytheus.com`
- [ ] Updated `README.md`
- [ ] Backup/restore instructions for data volumes

## Notification Channels
Slack, Telegram, Email (secondary), SMS via Twilio (optional). All configurable per-check and per-severity.

## Code Style
- Clear, well-commented code
- Meaningful commit messages
- No secrets in code — `.env` only
- Health checks on every container
