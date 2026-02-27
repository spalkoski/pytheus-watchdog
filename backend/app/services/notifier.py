import httpx
import logging
from typing import Dict, Any, List
from backend.app.core.config import settings, watchdog_config

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles sending notifications to various channels"""

    def __init__(self):
        self.config = watchdog_config.get("notifications", {})
        self.slack_config = self.config.get("slack", {})
        self.telegram_config = self.config.get("telegram", {})

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        target_name: str,
        channels: List[str],
        metadata: Dict[str, Any] = None
    ):
        """Send alert to specified channels"""
        metadata = metadata or {}

        for channel in channels:
            try:
                if channel == "slack" and self.slack_config.get("enabled"):
                    await self._send_slack(title, message, severity, target_name, metadata)
                elif channel == "telegram" and self.telegram_config.get("enabled"):
                    await self._send_telegram(title, message, severity, target_name, metadata)
                else:
                    logger.warning(f"Channel {channel} not configured or disabled")
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")

    async def _send_slack(
        self,
        title: str,
        message: str,
        severity: str,
        target_name: str,
        metadata: Dict[str, Any]
    ):
        """Send notification to Slack"""
        webhook_url = settings.slack_webhook_url
        if not webhook_url:
            logger.warning("Slack webhook URL not configured")
            return

        # Color based on severity
        color_map = {
            "critical": "#FF0000",  # Red
            "warning": "#FFA500",   # Orange
            "info": "#00FF00"       # Green
        }
        color = color_map.get(severity, "#808080")

        # Emoji based on severity
        emoji_map = {
            "critical": ":red_circle:",
            "warning": ":warning:",
            "info": ":information_source:"
        }
        emoji = emoji_map.get(severity, ":bell:")

        payload = {
            "channel": self.slack_config.get("channel", "#monitoring"),
            "username": "Pytheus Watchdog",
            "icon_emoji": ":robot_face:",
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} {title}",
                    "text": message,
                    "fields": [
                        {
                            "title": "Service",
                            "value": target_name,
                            "short": True
                        },
                        {
                            "title": "Severity",
                            "value": severity.upper(),
                            "short": True
                        }
                    ],
                    "footer": "Pytheus Watchdog",
                    "ts": metadata.get("timestamp", 0)
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Slack notification sent for {target_name}")

    async def _send_telegram(
        self,
        title: str,
        message: str,
        severity: str,
        target_name: str,
        metadata: Dict[str, Any]
    ):
        """Send notification to Telegram"""
        bot_token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id

        if not bot_token or not chat_id:
            logger.warning("Telegram bot token or chat ID not configured")
            return

        # Emoji based on severity
        emoji_map = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🟢"
        }
        emoji = emoji_map.get(severity, "🔔")

        # Format message with HTML
        text = f"""<b>{emoji} {title}</b>

{message}

<b>Service:</b> {target_name}
<b>Severity:</b> {severity.upper()}

<i>— Pytheus Watchdog</i>"""

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Telegram notification sent for {target_name}")

    async def send_recovery_alert(
        self,
        target_name: str,
        downtime_duration: str,
        channels: List[str]
    ):
        """Send recovery notification"""
        title = f"✅ Service Recovered: {target_name}"
        message = f"The service has recovered after {downtime_duration} of downtime."

        await self.send_alert(
            title=title,
            message=message,
            severity="info",
            target_name=target_name,
            channels=channels
        )

    async def send_daily_digest(
        self,
        target_statuses: List[Dict[str, Any]],
        deadman_statuses: List[Dict[str, Any]]
    ):
        """Send daily status digest to all enabled channels"""
        from datetime import datetime
        import pytz

        pacific_tz = pytz.timezone('America/Los_Angeles')
        now_pacific = datetime.now(pacific_tz)
        date_str = now_pacific.strftime("%A, %B %d, %Y")

        # Build status summary
        status_emoji = {
            "up": "🟢",
            "down": "🔴",
            "degraded": "🟡",
            "unknown": "⚪",
            "ok": "🟢",
            "overdue": "🟡",
            "critical": "🔴"
        }

        # Count statuses
        up_count = sum(1 for t in target_statuses if t["status"] == "up")
        down_count = sum(1 for t in target_statuses if t["status"] == "down")
        degraded_count = sum(1 for t in target_statuses if t["status"] == "degraded")
        total = len(target_statuses)

        # Overall health indicator
        if down_count > 0:
            overall_emoji = "🔴"
            overall_status = "Issues Detected"
        elif degraded_count > 0:
            overall_emoji = "🟡"
            overall_status = "Some Degradation"
        else:
            overall_emoji = "🟢"
            overall_status = "All Systems Operational"

        # Build target list
        target_lines = []
        for t in target_statuses:
            emoji = status_emoji.get(t["status"], "⚪")
            uptime_str = f"{t['uptime_24h']:.1f}%" if t['uptime_24h'] is not None else "N/A"
            target_lines.append(f"{emoji} {t['name']}: {t['status'].upper()} ({uptime_str} 24h)")

        # Build deadman switch list
        deadman_lines = []
        for d in deadman_statuses:
            emoji = status_emoji.get(d["status"], "⚪")
            deadman_lines.append(f"{emoji} {d['name']}: {d['status'].upper()}")

        # Telegram message
        if self.telegram_config.get("enabled"):
            telegram_text = f"""<b>📊 Daily Status Report</b>
<i>{date_str}</i>

<b>{overall_emoji} {overall_status}</b>
{up_count} up | {down_count} down | {degraded_count} degraded

<b>Services:</b>
{chr(10).join(target_lines)}"""

            if deadman_lines:
                telegram_text += f"""

<b>Dead Man's Switches:</b>
{chr(10).join(deadman_lines)}"""

            telegram_text += """

<i>— Pytheus Watchdog</i>"""

            await self._send_telegram_raw(telegram_text)

        # Slack message
        if self.slack_config.get("enabled"):
            await self._send_slack_digest(
                date_str, overall_emoji, overall_status,
                up_count, down_count, degraded_count,
                target_lines, deadman_lines
            )

    async def _send_telegram_raw(self, text: str):
        """Send raw HTML message to Telegram"""
        bot_token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id

        if not bot_token or not chat_id:
            logger.warning("Telegram not configured")
            return

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Telegram daily digest sent")

    async def _send_slack_digest(
        self,
        date_str: str,
        overall_emoji: str,
        overall_status: str,
        up_count: int,
        down_count: int,
        degraded_count: int,
        target_lines: List[str],
        deadman_lines: List[str]
    ):
        """Send daily digest to Slack"""
        webhook_url = settings.slack_webhook_url
        if not webhook_url:
            logger.warning("Slack webhook not configured")
            return

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Daily Status Report"}
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": date_str}]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{overall_emoji} {overall_status}*\n{up_count} up | {down_count} down | {degraded_count} degraded"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Services:*\n" + "\n".join(target_lines)
                }
            }
        ]

        if deadman_lines:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Dead Man's Switches:*\n" + "\n".join(deadman_lines)
                }
            })

        payload = {
            "channel": self.slack_config.get("channel", "#monitoring"),
            "username": "Pytheus Watchdog",
            "icon_emoji": ":robot_face:",
            "blocks": blocks
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Slack daily digest sent")


# Global notifier instance
notifier = NotificationService()
