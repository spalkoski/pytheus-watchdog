"""
Status Page Parser - Detects incidents and degraded states from status pages.

Supports common status page formats:
- Atlassian Statuspage (used by GitHub, etc.)
- Instatus (used by Replit, etc.)
- Custom status pages with common patterns
"""

import re
import json
import logging
from typing import Tuple, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Patterns that indicate problems (matched against page text)
INCIDENT_PATTERNS = [
    r"having issues",
    r"experiencing (problems|issues|difficulties)",
    r"currently (investigating|experiencing|failing)",
    r"service disruption",
    r"degraded performance",
    r"partial outage",
    r"major outage",
    r"incident",
    r"maintenance in progress",
    r"temporary issue",
    r"sorry for the disruption",
    r"failing to (load|start|connect|respond)",
    r"working to resolve",
]

# Patterns that indicate all is well
OPERATIONAL_PATTERNS = [
    r"all (systems|services) operational",
    r"no (issues|incidents)",
    r"everything.+operational",
]


def _check_instatus(soup: BeautifulSoup) -> list:
    """Detect incidents on Instatus-style pages (e.g. Replit)."""
    incidents = []

    # Instatus uses CSS classes like border-state-identified, border-state-investigating
    # on notice cards with id="notice-card-*"
    notice_cards = soup.find_all(id=re.compile(r'notice-card-', re.I))
    for card in notice_cards:
        classes = ' '.join(card.get('class', []))
        # Skip resolved notices
        if 'state-resolved' in classes:
            continue
        # Active states: identified, investigating, monitoring
        if re.search(r'state-(identified|investigating|monitoring|degraded)', classes):
            synopsis = card.find(class_=re.compile(r'synopsis', re.I))
            desc = synopsis.get_text(strip=True) if synopsis else card.get_text(strip=True)[:150]
            incidents.append(desc)

    # Also check for embedded JSON component states
    for script in soup.find_all('script'):
        script_text = script.string or ''
        # Look for state: "degraded" patterns in inline data
        if '"state"' in script_text:
            for match in re.finditer(r'"state"\s*:\s*"(degraded|major_outage|partial_outage)"', script_text):
                incidents.append(f"Component state: {match.group(1)}")
                break  # One match is enough

    return incidents


def _check_atlassian_statuspage(soup: BeautifulSoup) -> list:
    """Detect incidents on Atlassian Statuspage-style pages (e.g. GitHub)."""
    incidents = []

    # Component status indicators
    status_components = soup.find_all(class_=re.compile(r'component-status', re.I))
    for comp in status_components:
        comp_text = comp.get_text(strip=True).lower()
        if any(word in comp_text for word in ['degraded', 'partial', 'major', 'outage', 'incident']):
            parent = comp.find_parent(class_=re.compile(r'component', re.I))
            if parent:
                name = parent.find(class_=re.compile(r'name', re.I))
                if name:
                    incidents.append(f"Degraded: {name.get_text(strip=True)}")

    # Unresolved incidents
    unresolved = soup.find_all(class_=re.compile(r'unresolved|active-incident|current-incident', re.I))
    for incident in unresolved:
        title = incident.find(class_=re.compile(r'title|name', re.I))
        if title:
            incidents.append(title.get_text(strip=True))

    # Incident status labels (Identified, Investigating, etc.)
    incident_statuses = soup.find_all(string=re.compile(r'^(Identified|Investigating|Monitoring|Update)$', re.I))
    for status_el in incident_statuses:
        parent = status_el.find_parent(class_=re.compile(r'incident|notice|status', re.I))
        if parent:
            title = parent.find(class_=re.compile(r'title|name|message', re.I))
            if title:
                incidents.append(f"{status_el.strip()}: {title.get_text(strip=True)[:100]}")

    return incidents


def parse_status_page(html: str, url: str) -> Tuple[str, Optional[str]]:
    """
    Parse a status page and determine the actual status.

    Returns:
        Tuple of (status, description)
        - status: 'operational', 'degraded', 'major_outage', 'maintenance'
        - description: Brief description of any issues found
    """
    soup = BeautifulSoup(html, 'lxml')
    text_content = soup.get_text(separator=' ', strip=True).lower()

    incidents_found = []

    # Check for incident patterns in text
    for pattern in INCIDENT_PATTERNS:
        if re.search(pattern, text_content, re.I):
            match = re.search(rf'.{{0,100}}{pattern}.{{0,100}}', text_content, re.I)
            if match:
                incidents_found.append(match.group(0).strip())

    # Check platform-specific structures
    incidents_found.extend(_check_instatus(soup))
    incidents_found.extend(_check_atlassian_statuspage(soup))

    # Determine final status
    if incidents_found:
        description = "; ".join(set(incidents_found[:3]))

        # Check severity
        if any(word in text_content for word in ['major outage', 'service unavailable', 'completely down']):
            return 'major_outage', description
        elif any(word in text_content for word in ['maintenance']):
            return 'maintenance', description
        else:
            return 'degraded', description

    # Check if explicitly operational
    for pattern in OPERATIONAL_PATTERNS:
        if re.search(pattern, text_content, re.I):
            return 'operational', None

    # Default to operational if no issues found
    return 'operational', None


def check_status_page(html: str, url: str) -> dict:
    """
    Check a status page and return structured result.

    Returns:
        dict with keys: status, is_healthy, description
    """
    status, description = parse_status_page(html, url)

    is_healthy = status == 'operational'

    result = {
        'status': status,
        'is_healthy': is_healthy,
        'description': description,
    }

    if not is_healthy:
        logger.warning(f"Status page {url} shows issues: {status} - {description}")

    return result
