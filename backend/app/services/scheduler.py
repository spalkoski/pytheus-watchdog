import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from typing import Dict, Any
from datetime import datetime, timedelta
import pytz

from backend.app.services.monitor import monitor
from backend.app.services.notifier import notifier
from backend.app.core.config import watchdog_config
from backend.app.models.database import AsyncSessionLocal, DeadManSwitch, CheckResult
from sqlalchemy import select, desc, and_, func

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages scheduled monitoring jobs"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.target_configs = watchdog_config.get("targets", [])
        self.deadman_config = watchdog_config.get("deadman_switches", [])

    async def start(self):
        """Start the scheduler and register all monitoring jobs"""
        logger.info("Starting monitoring scheduler...")

        # Schedule HTTP target checks
        for target_config in self.target_configs:
            await self._schedule_target_check(target_config)

        # Schedule dead man's switch checks (every 60 seconds)
        self.scheduler.add_job(
            self._check_deadman_switches,
            trigger=IntervalTrigger(seconds=60),
            id="deadman_check",
            name="Dead Man's Switch Check",
            replace_existing=True
        )

        # Initialize dead man's switches in database
        await self._init_deadman_switches()

        # Schedule daily digest at 7am Pacific
        pacific_tz = pytz.timezone('America/Los_Angeles')
        self.scheduler.add_job(
            self._send_daily_digest,
            trigger=CronTrigger(hour=7, minute=0, timezone=pacific_tz),
            id="daily_digest",
            name="Daily Status Digest",
            replace_existing=True
        )
        logger.info("Scheduled daily digest for 7:00 AM Pacific")

        self.scheduler.start()
        logger.info(f"Scheduler started with {len(self.scheduler.get_jobs())} jobs")

    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping monitoring scheduler...")
        self.scheduler.shutdown(wait=False)

    async def _schedule_target_check(self, target_config: Dict[str, Any]):
        """Schedule a monitoring check for a target"""
        target_name = target_config["name"]
        interval = target_config.get("interval", 60)  # Default 60 seconds

        self.scheduler.add_job(
            self._run_target_check,
            trigger=IntervalTrigger(seconds=interval),
            args=[target_config],
            id=f"check_{target_name}",
            name=f"Check {target_name}",
            replace_existing=True
        )

        logger.info(f"Scheduled check for '{target_name}' every {interval}s")

    async def _run_target_check(self, target_config: Dict[str, Any]):
        """Run a single target check (job wrapper)"""
        async with AsyncSessionLocal() as db:
            try:
                check_type = target_config["type"]
                if check_type == "http":
                    await monitor.check_http_target(target_config, db)
                elif check_type == "ping":
                    await monitor.check_ping_target(target_config, db)
                else:
                    logger.warning(f"Unsupported target type: {check_type}")
                await db.commit()
            except Exception as e:
                logger.error(f"Error checking target {target_config['name']}: {e}")
                await db.rollback()

    async def _check_deadman_switches(self):
        """Check all dead man's switches (job wrapper)"""
        async with AsyncSessionLocal() as db:
            try:
                await monitor.check_deadman_switches(db)
                await db.commit()
            except Exception as e:
                logger.error(f"Error checking dead man's switches: {e}")
                await db.rollback()

    async def _init_deadman_switches(self):
        """Initialize dead man's switches from config into database"""
        async with AsyncSessionLocal() as db:
            try:
                for switch_config in self.deadman_config:
                    name = switch_config["name"]

                    # Check if already exists
                    result = await db.execute(
                        select(DeadManSwitch).where(DeadManSwitch.name == name)
                    )
                    existing = result.scalar_one_or_none()

                    if not existing:
                        # Generate unique token
                        import secrets
                        token = secrets.token_urlsafe(32)

                        deadman = DeadManSwitch(
                            name=name,
                            token=token,
                            expected_interval=switch_config["expected_interval"],
                            severity=switch_config.get("severity", "warning"),
                            enabled=True
                        )
                        db.add(deadman)
                        logger.info(f"Initialized dead man's switch: {name}")

                await db.commit()
            except Exception as e:
                logger.error(f"Error initializing dead man's switches: {e}")
                await db.rollback()

    async def _send_daily_digest(self):
        """Send daily status digest at 7am Pacific"""
        logger.info("Generating daily status digest...")

        async with AsyncSessionLocal() as db:
            try:
                # Get status for all targets
                target_statuses = []
                for target_config in self.target_configs:
                    target_name = target_config["name"]

                    # Get latest check
                    result = await db.execute(
                        select(CheckResult)
                        .where(CheckResult.target_name == target_name)
                        .order_by(desc(CheckResult.checked_at))
                        .limit(1)
                    )
                    latest_check = result.scalar_one_or_none()

                    # Calculate 24h uptime
                    since_24h = datetime.utcnow() - timedelta(hours=24)
                    total_result = await db.execute(
                        select(func.count(CheckResult.id))
                        .where(and_(
                            CheckResult.target_name == target_name,
                            CheckResult.checked_at >= since_24h
                        ))
                    )
                    total_checks = total_result.scalar() or 0

                    up_result = await db.execute(
                        select(func.count(CheckResult.id))
                        .where(and_(
                            CheckResult.target_name == target_name,
                            CheckResult.checked_at >= since_24h,
                            CheckResult.status == "up"
                        ))
                    )
                    up_checks = up_result.scalar() or 0

                    uptime_24h = (up_checks / total_checks * 100) if total_checks > 0 else 100.0

                    status = latest_check.status if latest_check else "unknown"
                    target_statuses.append({
                        "name": target_name,
                        "type": target_config["type"],
                        "status": status,
                        "uptime_24h": uptime_24h
                    })

                # Get dead man's switches status
                result = await db.execute(
                    select(DeadManSwitch).where(DeadManSwitch.enabled == True)
                )
                switches = result.scalars().all()

                deadman_statuses = []
                current_time = datetime.utcnow()
                for switch in switches:
                    status = "unknown"
                    if switch.last_ping:
                        time_since_ping = (current_time - switch.last_ping).total_seconds()
                        if time_since_ping < switch.expected_interval:
                            status = "ok"
                        elif time_since_ping < switch.expected_interval * 1.5:
                            status = "overdue"
                        else:
                            status = "critical"
                    deadman_statuses.append({
                        "name": switch.name,
                        "status": status
                    })

                # Send the digest
                await notifier.send_daily_digest(target_statuses, deadman_statuses)
                logger.info("Daily digest sent successfully")

            except Exception as e:
                logger.error(f"Error sending daily digest: {e}")


# Global scheduler instance
scheduler = SchedulerService()
