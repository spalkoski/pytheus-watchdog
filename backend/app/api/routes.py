from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from datetime import datetime, timedelta
from typing import List, Optional

from backend.app.models.database import (
    get_db,
    CheckResult,
    Incident,
    DeadManSwitch,
    DeadManPing
)
from backend.app.models.schemas import (
    DashboardData,
    TargetStatus,
    IncidentResponse,
    CheckResultResponse,
    DeadManSwitchResponse,
    DeadManPingRequest
)
from backend.app.services.monitor import monitor
from backend.app.core.config import watchdog_config

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Get dashboard overview data"""
    targets_config = watchdog_config.get("targets", [])
    target_statuses = []

    # Get status for each target
    for target_config in targets_config:
        target_name = target_config["name"]

        # Get latest check
        result = await db.execute(
            select(CheckResult)
            .where(CheckResult.target_name == target_name)
            .order_by(desc(CheckResult.checked_at))
            .limit(1)
        )
        latest_check = result.scalar_one_or_none()

        # Calculate uptime percentages
        uptime_24h = await monitor.calculate_uptime(target_name, 24, db)
        uptime_7d = await monitor.calculate_uptime(target_name, 24 * 7, db)
        uptime_30d = await monitor.calculate_uptime(target_name, 24 * 30, db)

        target_status = TargetStatus(
            name=target_name,
            type=target_config["type"],
            url=target_config.get("url"),
            status=latest_check.status if latest_check else "unknown",
            last_check=latest_check.checked_at if latest_check else None,
            response_time=latest_check.response_time if latest_check else None,
            uptime_24h=uptime_24h,
            uptime_7d=uptime_7d,
            uptime_30d=uptime_30d,
            ai_summary=latest_check.ai_summary if latest_check else None
        )
        target_statuses.append(target_status)

    # Get active incidents
    result = await db.execute(
        select(Incident)
        .where(Incident.status.in_(["open", "acknowledged"]))
        .order_by(desc(Incident.started_at))
    )
    active_incidents_raw = result.scalars().all()

    active_incidents = []
    for incident in active_incidents_raw:
        duration = None
        if incident.resolved_at:
            duration = int((incident.resolved_at - incident.started_at).total_seconds() / 60)
        elif incident.status == "open":
            duration = int((datetime.utcnow() - incident.started_at).total_seconds() / 60)

        active_incidents.append(
            IncidentResponse(
                id=incident.id,
                target_name=incident.target_name,
                severity=incident.severity,
                status=incident.status,
                title=incident.title,
                description=incident.description,
                started_at=incident.started_at,
                resolved_at=incident.resolved_at,
                duration_minutes=duration
            )
        )

    # Count checks in last 24h
    since_24h = datetime.utcnow() - timedelta(hours=24)
    result = await db.execute(
        select(func.count(CheckResult.id))
        .where(CheckResult.checked_at >= since_24h)
    )
    total_checks_24h = result.scalar() or 0

    # Calculate overall uptime
    result = await db.execute(
        select(func.count(CheckResult.id))
        .where(
            and_(
                CheckResult.checked_at >= since_24h,
                CheckResult.status == "up"
            )
        )
    )
    up_checks = result.scalar() or 0
    uptime_percentage = (up_checks / total_checks_24h * 100) if total_checks_24h > 0 else 100.0

    # Get dead man's switches
    result = await db.execute(select(DeadManSwitch))
    switches_raw = result.scalars().all()

    deadman_switches = []
    current_time = datetime.utcnow()
    for switch in switches_raw:
        # Determine status
        status = "unknown"
        if switch.last_ping:
            time_since_ping = (current_time - switch.last_ping).total_seconds()
            if time_since_ping < switch.expected_interval:
                status = "ok"
            elif time_since_ping < switch.expected_interval * 1.5:
                status = "overdue"
            else:
                status = "critical"

        deadman_switches.append(
            DeadManSwitchResponse(
                id=switch.id,
                name=switch.name,
                token=switch.token,
                expected_interval=switch.expected_interval,
                last_ping=switch.last_ping,
                status=status,
                enabled=switch.enabled
            )
        )

    return DashboardData(
        targets=target_statuses,
        active_incidents=active_incidents,
        total_checks_24h=total_checks_24h,
        uptime_percentage=uptime_percentage,
        deadman_switches=deadman_switches
    )


@router.get("/targets/{target_name}/history", response_model=List[CheckResultResponse])
async def get_target_history(
    target_name: str,
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """Get check history for a specific target"""
    since = datetime.utcnow() - timedelta(hours=hours)

    result = await db.execute(
        select(CheckResult)
        .where(
            and_(
                CheckResult.target_name == target_name,
                CheckResult.checked_at >= since
            )
        )
        .order_by(desc(CheckResult.checked_at))
        .limit(1000)
    )
    checks = result.scalars().all()

    return [CheckResultResponse.model_validate(check) for check in checks]


@router.get("/incidents", response_model=List[IncidentResponse])
async def get_incidents(
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get incidents, optionally filtered by status"""
    query = select(Incident).order_by(desc(Incident.started_at)).limit(limit)

    if status:
        query = query.where(Incident.status == status)

    result = await db.execute(query)
    incidents_raw = result.scalars().all()

    incidents = []
    for incident in incidents_raw:
        duration = None
        if incident.resolved_at:
            duration = int((incident.resolved_at - incident.started_at).total_seconds() / 60)
        elif incident.status == "open":
            duration = int((datetime.utcnow() - incident.started_at).total_seconds() / 60)

        incidents.append(
            IncidentResponse(
                id=incident.id,
                target_name=incident.target_name,
                severity=incident.severity,
                status=incident.status,
                title=incident.title,
                description=incident.description,
                started_at=incident.started_at,
                resolved_at=incident.resolved_at,
                duration_minutes=duration
            )
        )

    return incidents


@router.post("/incidents/{incident_id}/acknowledge")
async def acknowledge_incident(incident_id: int, db: AsyncSession = Depends(get_db)):
    """Acknowledge an incident"""
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "acknowledged"
    await db.commit()

    return {"status": "ok", "incident_id": incident_id}


@router.post("/ping/{token}")
async def deadman_ping(
    token: str,
    payload: DeadManPingRequest = None,
    db: AsyncSession = Depends(get_db)
):
    """Receive a dead man's switch ping"""
    # Find the switch by token
    result = await db.execute(
        select(DeadManSwitch).where(DeadManSwitch.token == token)
    )
    switch = result.scalar_one_or_none()

    if not switch:
        raise HTTPException(status_code=404, detail="Invalid token")

    if not switch.enabled:
        raise HTTPException(status_code=403, detail="Switch is disabled")

    # Update last ping time
    switch.last_ping = datetime.utcnow()

    # Record the ping
    ping = DeadManPing(
        switch_id=switch.id,
        switch_name=switch.name,
        pinged_at=datetime.utcnow(),
        payload=payload.metadata if payload else None
    )
    db.add(ping)

    # If there's an active incident for this switch, resolve it
    incident_key = f"deadman_{switch.name}"
    if incident_key in monitor.active_incidents:
        incident_id = monitor.active_incidents[incident_key]
        result = await db.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        incident = result.scalar_one_or_none()

        if incident:
            incident.status = "resolved"
            incident.resolved_at = datetime.utcnow()
            del monitor.active_incidents[incident_key]

    await db.commit()

    return {
        "status": "ok",
        "switch": switch.name,
        "timestamp": switch.last_ping.isoformat()
    }


@router.get("/deadman/{switch_name}/webhook-url")
async def get_webhook_url(switch_name: str, db: AsyncSession = Depends(get_db)):
    """Get the webhook URL for a dead man's switch"""
    result = await db.execute(
        select(DeadManSwitch).where(DeadManSwitch.name == switch_name)
    )
    switch = result.scalar_one_or_none()

    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")

    # In production, use actual domain
    base_url = "https://watchdog.pytheus.com"
    webhook_url = f"{base_url}/api/ping/{switch.token}"

    return {
        "switch": switch_name,
        "webhook_url": webhook_url,
        "token": switch.token
    }
