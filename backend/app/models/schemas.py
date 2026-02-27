from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class TargetStatus(BaseModel):
    """Current status of a monitored target"""
    name: str
    type: str
    url: Optional[str]  # Link to the monitored service
    status: str  # up, down, degraded
    last_check: Optional[datetime]
    response_time: Optional[float]
    uptime_24h: Optional[float]
    uptime_7d: Optional[float]
    uptime_30d: Optional[float]
    ai_summary: Optional[str] = None  # AI triage reasoning for status pages


class CheckResultResponse(BaseModel):
    """Check result API response"""
    id: int
    target_name: str
    status: str
    response_time: Optional[float]
    status_code: Optional[int]
    error_message: Optional[str]
    checked_at: datetime

    class Config:
        from_attributes = True


class IncidentResponse(BaseModel):
    """Incident API response"""
    id: int
    target_name: str
    severity: str
    status: str
    title: str
    description: str
    started_at: datetime
    resolved_at: Optional[datetime]
    duration_minutes: Optional[int]

    class Config:
        from_attributes = True


class DeadManSwitchResponse(BaseModel):
    """Dead man's switch API response"""
    id: int
    name: str
    token: str
    expected_interval: int
    last_ping: Optional[datetime]
    status: str  # ok, overdue, critical
    enabled: bool

    class Config:
        from_attributes = True


class DeadManPingRequest(BaseModel):
    """Dead man's switch ping request"""
    metadata: Optional[Dict[str, Any]] = None


class DashboardData(BaseModel):
    """Dashboard overview data"""
    targets: List[TargetStatus]
    active_incidents: List[IncidentResponse]
    total_checks_24h: int
    uptime_percentage: float
    deadman_switches: List[DeadManSwitchResponse]
