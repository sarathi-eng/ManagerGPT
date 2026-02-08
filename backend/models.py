from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    user_goal: str = Field(..., min_length=1)


class GoalRequest(BaseModel):
    goal: str = Field(..., min_length=1)
    business_name: Optional[str] = None
    competitor_names: Optional[List[str]] = None
    vendor_names: Optional[List[str]] = None


class SessionSummary(BaseModel):
    id: int
    user_goal: str
    status: str
    final_decision: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class TaskCreate(BaseModel):
    description: str = Field(..., min_length=1)
    task_number: int


class TaskSummary(BaseModel):
    id: int
    session_id: int
    task_number: int
    description: str
    status: str
    created_at: datetime


class ResearchFindingCreate(BaseModel):
    task_id: int
    findings: str = Field(..., min_length=1)
    sources: Optional[List[str]] = None
    confidence: Optional[float] = None
    attempt_number: int = 1


class AnalysisResultCreate(BaseModel):
    session_id: int
    recommendation: Optional[str] = None
    reasoning: str = Field(..., min_length=1)
    confidence: Optional[float] = None


class CritiqueCreate(BaseModel):
    analysis_id: int
    approved: bool
    issues: Optional[List[str]] = None
    confidence_adjustment: Optional[float] = None


class AgentLogCreate(BaseModel):
    session_id: int
    agent_name: str
    message: str
    status: Optional[str] = None
    metadata: Optional[dict] = None


class OrchestrationResult(BaseModel):
    session: SessionSummary
    tasks: List[TaskSummary]
