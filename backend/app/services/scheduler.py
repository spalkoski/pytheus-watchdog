import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Dict, Any
from datetime import datetime

from backend.app.services.monitor import monitor
from backend.app.core.config import watchdog_config
from backend.app.models.database import AsyncSessionLocal, DeadManSwitch
from sqlalchemy import select

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
                if target_config["type"] == "http":
                    await monitor.check_http_target(target_config, db)
                else:
                    logger.warning(f"Unsupported target type: {target_config['type']}")
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


# Global scheduler instance
scheduler = SchedulerService()
