"""
Status Page Parser - Detects incidents and degraded states from status pages.

Supports common status page formats:
- Atlassian Statuspage (used by Replit, GitHub, etc.)
- Custom status pages with common patterns
"""

import re
import logging
from typing import Tuple, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Patterns that indicate problems
INCIDENT_PATTERNS = [
    r"having issues",
    r"experiencing (problems|issues|difficulties)",
    r"currently (investigating|experiencing)",
    r"service disruption",
    r"degraded performance",
    r"partial outage",
    r"major outage",
    r"incident",
    r"maintenance in progress",
]

# Patterns that indicate all is well
OPERATIONAL_PATTERNS = [
    r"all (systems|services) operational",
    r"no (issues|incidents)",
    r"everything.+operational",
]


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

    # Check for incident banners/notices (common in Atlassian Statuspage)
    incident_elements = soup.find_all(class_=re.compile(r'(incident|notice|alert|warning|banner)', re.I))

    # Look for active incidents section
    incidents_found = []

    # Check for incident patterns in text
    for pattern in INCIDENT_PATTERNS:
        if re.search(pattern, text_content, re.I):
            # Try to extract the incident description
            match = re.search(rf'.{{0,100}}{pattern}.{{0,100}}', text_content, re.I)
            if match:
                incidents_found.append(match.group(0).strip())

    # Check for specific status page structures

    # Atlassian Statuspage format (used by Replit, many others)
    status_components = soup.find_all(class_=re.compile(r'component-status', re.I))
    degraded_components = []
    for comp in status_components:
        comp_text = comp.get_text(strip=True).lower()
        if any(word in comp_text for word in ['degraded', 'partial', 'major', 'outage', 'incident']):
            parent = comp.find_parent(class_=re.compile(r'component', re.I))
            if parent:
                name = parent.find(class_=re.compile(r'name', re.I))
                if name:
                    degraded_components.append(name.get_text(strip=True))

    # Check for unresolved incidents (Statuspage format)
    unresolved = soup.find_all(class_=re.compile(r'unresolved|active-incident|current-incident', re.I))
    if unresolved:
        for incident in unresolved:
            title = incident.find(class_=re.compile(r'title|name', re.I))
            if title:
                incidents_found.append(title.get_text(strip=True))

    # Check for incident container with "Identified" or "Investigating" status
    incident_statuses = soup.find_all(string=re.compile(r'^(Identified|Investigating|Monitoring|Update)$', re.I))
    for status_el in incident_statuses:
        parent = status_el.find_parent(class_=re.compile(r'incident|notice|status', re.I))
        if parent:
            title = parent.find(class_=re.compile(r'title|name|message', re.I))
            if title:
                incidents_found.append(f"{status_el.strip()}: {title.get_text(strip=True)[:100]}")

    # Check for warning/incident colored elements (orange/red backgrounds)
    warning_elements = soup.find_all(style=re.compile(r'(orange|#f[a-f0-9]{2}[0-9a-f]{3}|warning|error)', re.I))

    # Determine final status
    if incidents_found or degraded_components or unresolved:
        description = "; ".join(set(incidents_found[:3])) if incidents_found else None
        if degraded_components:
            description = f"Degraded: {', '.join(degraded_components[:3])}"

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
