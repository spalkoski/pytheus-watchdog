"""
AI Triage Service - Uses Claude to confirm and analyze platform issues.
"""

import logging
from typing import Optional, Dict, Any
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class AITriageService:
    """AI-powered triage for platform issue confirmation"""

    def __init__(self):
        self.enabled = bool(settings.anthropic_api_key)
        if self.enabled:
            self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            logger.info("AI Triage enabled with Claude")
        else:
            self.client = None
            logger.warning("AI Triage disabled - no ANTHROPIC_API_KEY configured")

    async def confirm_platform_issue(
        self,
        platform_name: str,
        status_page_url: str,
        html_content: str,
        parser_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use AI to confirm if there's actually a platform issue.

        Returns:
            dict with keys:
            - confirmed: bool - whether AI confirms the issue
            - severity: str - 'critical', 'warning', 'info'
            - summary: str - brief human-readable summary
            - affects_users: bool - whether this likely affects users
            - recommendation: str - what to do
        """
        if not self.enabled:
            # If AI is disabled, trust the parser result
            return {
                'confirmed': True,
                'severity': 'warning',
                'summary': parser_result.get('description', 'Platform issue detected'),
                'affects_users': True,
                'recommendation': 'Monitor the situation'
            }

        try:
            # Extract readable text from HTML
            soup = BeautifulSoup(html_content, 'lxml')

            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()

            page_text = soup.get_text(separator='\n', strip=True)
            # Limit to first 4000 chars to stay within token limits
            page_text = page_text[:4000]

            prompt = f"""You are a monitoring system analyzing a platform status page to determine if there's an actual issue that would affect users.

Platform: {platform_name}
Status Page URL: {status_page_url}

Our automated parser detected: {parser_result.get('status', 'unknown')}
Parser description: {parser_result.get('description', 'No details')}

Here is the text content from the status page:
---
{page_text}
---

Analyze this status page and respond with a JSON object (no markdown, just raw JSON):
{{
  "confirmed": true/false,  // Is there actually an ongoing issue?
  "severity": "critical|warning|info",  // How severe is the issue?
  "summary": "Brief 1-2 sentence summary of the issue",
  "affects_users": true/false,  // Does this affect regular users?
  "recommendation": "What should the user do?"
}}

Important:
- "confirmed" should be true only if there's a CURRENT, ACTIVE issue (not resolved or scheduled maintenance in the future)
- "severity" should be "critical" only for major outages, "warning" for degraded performance, "info" for minor issues
- If it's just scheduled maintenance that hasn't started, set confirmed to false
- If all systems show operational/green, set confirmed to false
- Be concise in your summary"""

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse the response
            response_text = response.content[0].text.strip()

            # Try to parse as JSON
            import json
            try:
                result = json.loads(response_text)
                logger.info(f"AI triage for {platform_name}: confirmed={result.get('confirmed')}, severity={result.get('severity')}")
                return result
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract key info
                logger.warning(f"Failed to parse AI response as JSON: {response_text[:200]}")
                return {
                    'confirmed': True,
                    'severity': 'warning',
                    'summary': parser_result.get('description', 'Platform issue detected'),
                    'affects_users': True,
                    'recommendation': 'Check the status page manually'
                }

        except Exception as e:
            logger.error(f"AI triage failed for {platform_name}: {e}")
            # On error, fall back to parser result
            return {
                'confirmed': True,
                'severity': 'warning',
                'summary': parser_result.get('description', 'Platform issue detected (AI unavailable)'),
                'affects_users': True,
                'recommendation': 'Check the status page manually'
            }


# Global instance
ai_triage = AITriageService()
