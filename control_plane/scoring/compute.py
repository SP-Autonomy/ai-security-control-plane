"""
Posture score computation
"""

from datetime import datetime
from sqlalchemy.orm import Session
from control_plane.api.models import Agent, PostureScore, Event, Tool, Policy


def compute_posture_score(agent_id: int, db: Session) -> PostureScore:
    """Compute posture score for an agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise ValueError("Agent not found")
    
    # Registry score (20 points)
    registry_score = 0
    if agent.nhi_id:
        registry_score += 10
    if agent.owner:
        registry_score += 5
    if agent.environment in ["staging", "production"]:
        registry_score += 5
    
    # Tools score (20 points)
    tools_score = 0
    if agent.allowed_tools:
        tools_score += 10
    if agent.budget_per_day > 0:
        tools_score += 5
    if agent.memory_scope:
        tools_score += 5
    
    # Tracing score (20 points)
    recent_events = db.query(Event).filter(Event.agent_id == agent_id).count()
    tracing_score = min(20, (recent_events / 10) * 20)
    
    # DLP score (20 points)
    dlp_score = 15  # Assume enabled by default
    
    # Policy score (20 points)
    enabled_policies = db.query(Policy).filter(Policy.enabled == True).count()
    policy_score = min(20, (enabled_policies / 3) * 20)
    
    overall_score = registry_score + tools_score + tracing_score + dlp_score + policy_score
    
    # Failing checks
    failing_checks = []
    recommendations = []
    
    if not agent.nhi_id:
        failing_checks.append("missing_nhi")
        recommendations.append({"check": "missing_nhi", "message": "Add NHI credential (SPIFFE ID)"})
    
    if not agent.allowed_tools:
        failing_checks.append("no_tools")
        recommendations.append({"check": "no_tools", "message": "Configure allowed tools list"})
    
    if recent_events < 10:
        failing_checks.append("low_trace_coverage")
        recommendations.append({"check": "low_trace_coverage", "message": "Ensure OTel traces are emitted"})
    
    # Create posture score record
    score = PostureScore(
        agent_id=agent_id,
        timestamp=datetime.utcnow(),
        overall_score=int(overall_score),
        registry_score=registry_score,
        tools_score=tools_score,
        tracing_score=int(tracing_score),
        dlp_score=dlp_score,
        policy_score=int(policy_score),
        failing_checks=failing_checks,
        recommendations=recommendations
    )
    
    db.add(score)
    db.commit()
    db.refresh(score)
    
    return score
