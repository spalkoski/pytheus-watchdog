import httpx
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.database import CheckResult, Incident, Target, DeadManSwitch
from backend.app.services.notifier import notifier
from backend.app.services.status_parser import check_status_page
from backend.app.services.ai_triage import ai_triage
from backend.app.core.config import watchdog_config

logger = logging.getLogger(__name__)


class MonitoringService:
    """Core monitoring engine"""

    def __init__(self):
        self.retry_config = watchdog_config.get("retry", {})
        self.max_attempts = self.retry_config.get("max_attempts", 3)
        self.delay_seconds = self.retry_config.get("delay_seconds", 10)
        self.backoff_multiplier = self.retry_config.get("backoff_multiplier", 1.5)
        self.active_incidents: Dict[str, int] = {}  # target_name -> incident_id

    def _is_status_page(self, target_config: Dict[str, Any]) -> bool:
        """Check if target is a status page that needs content parsing"""
        name = target_config.get("name", "").lower()
        url = target_config.get("url", "").lower()
        is_status = target_config.get("parse_status", False)

        # Auto-detect status pages
        if "status" in name or "status." in url or is_status:
            return True
        return False

    async def check_http_target(
        self,
        target_config: Dict[str, Any],
        db: AsyncSession
    ) -> CheckResult:
        """Perform HTTP check with retry logic and status page parsing"""
        target_name = target_config["name"]
        url = target_config["url"]
        timeout = target_config.get("timeout", 10)
        expected_status = target_config.get("expected_status", 200)
        content_match = target_config.get("content_match")
        is_status_page = self._is_status_page(target_config)

        logger.info(f"Checking target: {target_name} ({url})" + (" [status page]" if is_status_page else ""))

        # Retry loop
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                start_time = datetime.utcnow()

                async with httpx.AsyncClient(follow_redirects=True) as client:
                    response = await client.get(url, timeout=timeout)

                end_time = datetime.utcnow()
                response_time = (end_time - start_time).total_seconds() * 1000  # ms

                # Check status code
                if response.status_code != expected_status:
                    raise Exception(f"Unexpected status code: {response.status_code}")

                # Check content match if specified
                if content_match and content_match not in response.text:
                    raise Exception(f"Content match failed: '{content_match}' not found in response")

                # For status pages, parse the content to detect issues
                final_status = "up"
                error_msg = None
                status_result = None
                html_content = response.text
                ai_confirmed = False
                ai_summary = None

                if is_status_page:
                    status_result = check_status_page(html_content, url)
                    if not status_result['is_healthy']:
                        parser_desc = f"Platform issue: {status_result['status']}"
                        if status_result['description']:
                            parser_desc += f" - {status_result['description'][:200]}"
                        logger.warning(f"⚠ {target_name} parser detected issues: {parser_desc}")

                        # Use AI to confirm before setting degraded
                        ai_confirmed, ai_summary = await self._handle_degraded(
                            target_name, parser_desc, db, target_config,
                            html_content=html_content,
                            parser_result=status_result
                        )

                        if ai_confirmed:
                            final_status = "degraded"
                            error_msg = parser_desc

                # Record result
                check_result = CheckResult(
                    target_name=target_name,
                    status=final_status,
                    response_time=response_time,
                    status_code=response.status_code,
                    error_message=error_msg,
                    ai_summary=ai_summary,
                    checked_at=datetime.utcnow()
                )

                db.add(check_result)
                await db.flush()

                # Log status
                if final_status == "degraded":
                    logger.warning(f"⚠ {target_name} is DEGRADED ({response_time:.0f}ms)")
                    return check_result

                # Check if this is a recovery from an incident
                if target_name in self.active_incidents:
                    await self._resolve_incident(target_name, db, target_config)

                logger.info(f"✓ {target_name} is UP ({response_time:.0f}ms)")
                return check_result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt}/{self.max_attempts} failed for {target_name}: {last_error}")

                if attempt < self.max_attempts:
                    delay = self.delay_seconds * (self.backoff_multiplier ** (attempt - 1))
                    await asyncio.sleep(delay)

        # All retries failed
        check_result = CheckResult(
            target_name=target_name,
            status="down",
            response_time=None,
            status_code=None,
            error_message=last_error,
            checked_at=datetime.utcnow()
        )

        db.add(check_result)
        await db.flush()

        # Create or update incident
        await self._handle_failure(target_name, last_error, db, target_config)

        logger.error(f"✗ {target_name} is DOWN: {last_error}")
        return check_result

    async def _handle_failure(
        self,
        target_name: str,
        error_message: str,
        db: AsyncSession,
        target_config: Dict[str, Any]
    ):
        """Handle target failure - create incident and send notifications"""
        # Check if there's already an active incident
        if target_name in self.active_incidents:
            # Update existing incident retry count
            incident_id = self.active_incidents[target_name]
            result = await db.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = result.scalar_one_or_none()

            if incident:
                incident.retry_count += 1
                await db.flush()
                logger.info(f"Updated incident #{incident_id} for {target_name} (retry {incident.retry_count})")
            return

        # Create new incident
        severity = target_config.get("severity", "warning")
        incident = Incident(
            target_name=target_name,
            severity=severity,
            status="open",
            title=f"{target_name} is DOWN",
            description=f"Service check failed after {self.max_attempts} attempts.\n\nError: {error_message}",
            started_at=datetime.utcnow(),
            notification_sent=False,
            retry_count=self.max_attempts
        )

        db.add(incident)
        await db.flush()

        self.active_incidents[target_name] = incident.id
        logger.info(f"Created incident #{incident.id} for {target_name}")

        # Send notifications
        alert_channels = target_config.get("alerts", ["slack", "telegram"])
        await notifier.send_alert(
            title=f"🚨 Alert: {target_name} is DOWN",
            message=f"Service check failed after {self.max_attempts} attempts.\n\n**Error:** {error_message}",
            severity=severity,
            target_name=target_name,
            channels=alert_channels,
            metadata={"timestamp": int(datetime.utcnow().timestamp())}
        )

        incident.notification_sent = True
        await db.flush()

    async def _handle_degraded(
        self,
        target_name: str,
        description: str,
        db: AsyncSession,
        target_config: Dict[str, Any],
        html_content: str = None,
        parser_result: Dict[str, Any] = None
    ) -> tuple[bool, Optional[str]]:
        """Handle degraded status (platform issues detected) with AI confirmation.

        Returns:
            Tuple of (confirmed, ai_summary):
            - confirmed: True if the issue was confirmed (incident created or already exists)
            - ai_summary: AI's reasoning/summary about the status
        """
        # Check if there's already an active incident
        if target_name in self.active_incidents:
            return True, "Active incident already being tracked"

        # Use AI to confirm the issue before alerting
        url = target_config.get("url", "")
        ai_result = await ai_triage.confirm_platform_issue(
            platform_name=target_name,
            status_page_url=url,
            html_content=html_content or "",
            parser_result=parser_result or {"status": "degraded", "description": description}
        )

        ai_summary = ai_result.get('summary', 'No details available')

        if not ai_result.get('confirmed', True):
            logger.info(f"AI triage did NOT confirm issue for {target_name}: {ai_summary}")
            return False, f"AI Analysis: {ai_summary}"

        logger.info(f"AI triage CONFIRMED issue for {target_name}: {ai_summary}")

        # Use AI-determined severity, default to warning
        severity = ai_result.get('severity', 'warning')
        ai_summary = ai_result.get('summary', description)
        recommendation = ai_result.get('recommendation', 'Monitor the situation')

        # Create new incident for degraded service
        incident = Incident(
            target_name=target_name,
            severity=severity,
            status="open",
            title=f"{target_name} - Platform Issues Detected",
            description=f"{ai_summary}\n\nRecommendation: {recommendation}",
            started_at=datetime.utcnow(),
            notification_sent=False,
            retry_count=0
        )

        db.add(incident)
        await db.flush()

        self.active_incidents[target_name] = incident.id
        logger.info(f"Created degraded incident #{incident.id} for {target_name}")

        # Send notification with AI-enhanced message
        alert_channels = target_config.get("alerts", ["slack", "telegram"])
        await notifier.send_alert(
            title=f"⚠️ Platform Issue: {target_name}",
            message=f"**AI-Confirmed Issue:**\n\n{ai_summary}\n\n**Recommendation:** {recommendation}\n\n_This is a platform issue, not your code._",
            severity=severity,
            target_name=target_name,
            channels=alert_channels,
            metadata={"timestamp": int(datetime.utcnow().timestamp())}
        )

        incident.notification_sent = True
        await db.flush()
        return True, f"AI Confirmed: {ai_summary}"

    async def _resolve_incident(
        self,
        target_name: str,
        db: AsyncSession,
        target_config: Dict[str, Any]
    ):
        """Resolve an active incident"""
        if target_name not in self.active_incidents:
            return

        incident_id = self.active_incidents[target_name]
        result = await db.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        incident = result.scalar_one_or_none()

        if not incident:
            del self.active_incidents[target_name]
            return

        incident.status = "resolved"
        incident.resolved_at = datetime.utcnow()
        await db.flush()

        # Calculate downtime duration
        duration = incident.resolved_at - incident.started_at
        duration_str = str(duration).split('.')[0]  # Remove microseconds

        logger.info(f"Resolved incident #{incident_id} for {target_name} (downtime: {duration_str})")

        # Send recovery notification
        alert_channels = target_config.get("alerts", ["slack", "telegram"])
        await notifier.send_recovery_alert(
            target_name=target_name,
            downtime_duration=duration_str,
            channels=alert_channels
        )

        del self.active_incidents[target_name]

    async def check_deadman_switches(self, db: AsyncSession):
        """Check all dead man's switches for overdue pings"""
        result = await db.execute(
            select(DeadManSwitch).where(DeadManSwitch.enabled == True)
        )
        switches = result.scalars().all()

        current_time = datetime.utcnow()

        for switch in switches:
            if not switch.last_ping:
                # Never pinged yet - skip for now (grace period on first deployment)
                continue

            time_since_ping = (current_time - switch.last_ping).total_seconds()
            expected_interval = switch.expected_interval

            if time_since_ping > expected_interval:
                # Overdue!
                overdue_minutes = int((time_since_ping - expected_interval) / 60)
                logger.warning(f"Dead man's switch '{switch.name}' is overdue by {overdue_minutes} minutes")

                # Check if we already have an active incident
                incident_key = f"deadman_{switch.name}"
                if incident_key not in self.active_incidents:
                    # Create incident
                    incident = Incident(
                        target_name=switch.name,
                        severity=switch.severity,
                        status="open",
                        title=f"Dead Man's Switch Missed: {switch.name}",
                        description=f"Expected ping within {expected_interval}s, but it's been {int(time_since_ping)}s since last ping (overdue by {overdue_minutes} minutes).",
                        started_at=current_time,
                        notification_sent=False
                    )

                    db.add(incident)
                    await db.flush()

                    self.active_incidents[incident_key] = incident.id

                    # Send alert
                    await notifier.send_alert(
                        title=f"⏰ Dead Man's Switch Missed: {switch.name}",
                        message=f"Expected ping within {expected_interval}s, but it's been {int(time_since_ping)}s since last ping.\n\n**Overdue by:** {overdue_minutes} minutes",
                        severity=switch.severity,
                        target_name=switch.name,
                        channels=["slack", "telegram"],
                        metadata={"timestamp": int(current_time.timestamp())}
                    )

                    incident.notification_sent = True
                    await db.flush()

    async def calculate_uptime(
        self,
        target_name: str,
        hours: int,
        db: AsyncSession
    ) -> float:
        """Calculate uptime percentage for a target over specified hours"""
        since = datetime.utcnow() - timedelta(hours=hours)

        # Count total checks
        total_result = await db.execute(
            select(func.count(CheckResult.id))
            .where(
                and_(
                    CheckResult.target_name == target_name,
                    CheckResult.checked_at >= since
                )
            )
        )
        total_checks = total_result.scalar() or 0

        if total_checks == 0:
            return 100.0

        # Count successful checks
        up_result = await db.execute(
            select(func.count(CheckResult.id))
            .where(
                and_(
                    CheckResult.target_name == target_name,
                    CheckResult.checked_at >= since,
                    CheckResult.status == "up"
                )
            )
        )
        up_checks = up_result.scalar() or 0

        return (up_checks / total_checks) * 100.0


# Global monitoring service instance
monitor = MonitoringService()
