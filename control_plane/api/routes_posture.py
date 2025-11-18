"""
Security Posture API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from control_plane.api.init_db import get_db
from control_plane.api.models import PostureScore, PostureScoreSchema, Agent, Event, Policy

router = APIRouter()


class PostureScoreCreate(BaseModel):
    agent_id: int
    overall_score: int
    registry_score: int
    tools_score: int
    tracing_score: int
    dlp_score: int
    policy_score: int
    failing_checks: List[str] = []
    recommendations: List[dict] = []


@router.post("", response_model=PostureScoreSchema, status_code=201)
def create_posture_score(score: PostureScoreCreate, db: Session = Depends(get_db)):
    """Create a posture score"""
    
    # Check agent exists
    agent = db.query(Agent).filter(Agent.id == score.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    db_score = PostureScore(
        agent_id=score.agent_id,
        overall_score=score.overall_score,
        registry_score=score.registry_score,
        tools_score=score.tools_score,
        tracing_score=score.tracing_score,
        dlp_score=score.dlp_score,
        policy_score=score.policy_score,
        failing_checks=score.failing_checks,
        recommendations=score.recommendations
    )
    
    db.add(db_score)
    db.commit()
    db.refresh(db_score)
    
    return PostureScoreSchema.from_orm(db_score)


@router.get("", response_model=List[PostureScoreSchema])
def list_posture_scores(
    agent_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List posture scores with optional filtering"""
    
    query = db.query(PostureScore)
    
    if agent_id:
        query = query.filter(PostureScore.agent_id == agent_id)
    
    scores = query.order_by(PostureScore.timestamp.desc()).limit(limit).all()
    
    return [PostureScoreSchema.from_orm(score) for score in scores]


@router.get("/agent/{agent_id}/latest", response_model=PostureScoreSchema)
def get_latest_posture_score(agent_id: int, db: Session = Depends(get_db)):
    """Get latest posture score for an agent"""
    
    score = db.query(PostureScore).filter(
        PostureScore.agent_id == agent_id
    ).order_by(PostureScore.timestamp.desc()).first()
    
    if not score:
        raise HTTPException(status_code=404, detail="No posture scores found for agent")
    
    return PostureScoreSchema.from_orm(score)


@router.get("/agent/{agent_id}/trend")
def get_posture_trend(agent_id: int, days: int = 7, db: Session = Depends(get_db)):
    """Get posture score trend for an agent"""
    
    since = datetime.utcnow() - timedelta(days=days)
    
    scores = db.query(PostureScore).filter(
        PostureScore.agent_id == agent_id,
        PostureScore.timestamp >= since
    ).order_by(PostureScore.timestamp).all()
    
    if not scores:
        raise HTTPException(status_code=404, detail="No posture scores found")
    
    return {
        "agent_id": agent_id,
        "period_days": days,
        "data_points": len(scores),
        "scores": [
            {
                "timestamp": score.timestamp.isoformat(),
                "overall_score": score.overall_score,
                "registry_score": score.registry_score,
                "tools_score": score.tools_score,
                "tracing_score": score.tracing_score,
                "dlp_score": score.dlp_score,
                "policy_score": score.policy_score
            }
            for score in scores
        ]
    }


@router.post("/calculate/{agent_id}")
def calculate_posture_score(agent_id: int, db: Session = Depends(get_db)):
    """Calculate and save posture score for an agent"""
    
    # Check agent exists
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Calculate scores
    failing_checks = []
    recommendations = []
    
    # 1. Registry Score (20 points)
    registry_score = 20
    if not agent.nhi_id:
        registry_score -= 10
        failing_checks.append("missing_nhi_id")
        recommendations.append({"check": "nhi_id", "message": "Add NHI ID for agent"})
    if not agent.owner:
        registry_score -= 5
        failing_checks.append("missing_owner")
        recommendations.append({"check": "owner", "message": "Assign agent owner"})
    if not agent.description:
        registry_score -= 5
        failing_checks.append("missing_description")
    
    # 2. Tools Score (20 points)
    tools_score = 20
    if not agent.allowed_tools or len(agent.allowed_tools) == 0:
        tools_score -= 10
        failing_checks.append("no_tools_configured")
        recommendations.append({"check": "tools", "message": "Configure allowed tools"})
    if len(agent.allowed_tools) > 10:
        tools_score -= 5
        failing_checks.append("too_many_tools")
        recommendations.append({"check": "tools", "message": "Reduce number of allowed tools"})
    
    # 3. Tracing Score (20 points)
    tracing_score = 20
    recent_events = db.query(Event).filter(
        Event.agent_id == agent_id,
        Event.timestamp >= datetime.utcnow() - timedelta(days=1)
    ).all()
    
    if recent_events:
        traced_events = [e for e in recent_events if e.trace_id]
        trace_coverage = len(traced_events) / len(recent_events) * 100
        
        if trace_coverage < 50:
            tracing_score -= 15
            failing_checks.append("low_trace_coverage")
            recommendations.append({"check": "tracing", "message": "Improve trace ID coverage"})
        elif trace_coverage < 90:
            tracing_score -= 5
            failing_checks.append("medium_trace_coverage")
    
    # 4. DLP Score (20 points)
    dlp_score = 20
    dlp_policy = db.query(Policy).filter(Policy.name == "DLP Guard").first()
    if not dlp_policy or not dlp_policy.enabled:
        dlp_score -= 20
        failing_checks.append("dlp_disabled")
        recommendations.append({"check": "dlp", "message": "Enable DLP Guard policy"})
    
    # 5. Policy Score (20 points)
    policy_score = 20
    enabled_policies = db.query(Policy).filter(Policy.enabled == True).count()
    total_policies = db.query(Policy).count()
    
    if total_policies > 0:
        policy_ratio = enabled_policies / total_policies
        if policy_ratio < 0.5:
            policy_score -= 15
            failing_checks.append("few_policies_enabled")
            recommendations.append({"check": "policies", "message": "Enable more policies"})
        elif policy_ratio < 0.8:
            policy_score -= 5
    
    # Overall score
    overall_score = registry_score + tools_score + tracing_score + dlp_score + policy_score
    
    # Save score
    db_score = PostureScore(
        agent_id=agent_id,
        overall_score=overall_score,
        registry_score=registry_score,
        tools_score=tools_score,
        tracing_score=tracing_score,
        dlp_score=dlp_score,
        policy_score=policy_score,
        failing_checks=failing_checks,
        recommendations=recommendations
    )
    
    db.add(db_score)
    db.commit()
    db.refresh(db_score)
    
    return {
        "status": "success",
        "agent_id": agent_id,
        "overall_score": overall_score,
        "breakdown": {
            "registry": registry_score,
            "tools": tools_score,
            "tracing": tracing_score,
            "dlp": dlp_score,
            "policy": policy_score
        },
        "failing_checks": failing_checks,
        "recommendations": recommendations
    }


@router.get("/summary")
def get_posture_summary(db: Session = Depends(get_db)):
    """Get overall posture summary across all agents"""
    
    # Get latest score for each agent
    agents = db.query(Agent).all()
    
    summary = []
    total_score = 0
    count = 0
    
    for agent in agents:
        latest_score = db.query(PostureScore).filter(
            PostureScore.agent_id == agent.id
        ).order_by(PostureScore.timestamp.desc()).first()
        
        if latest_score:
            summary.append({
                "agent_id": agent.id,
                "agent_name": agent.name,
                "overall_score": latest_score.overall_score,
                "last_calculated": latest_score.timestamp.isoformat()
            })
            total_score += latest_score.overall_score
            count += 1
    
    avg_score = round(total_score / count) if count > 0 else 0
    
    return {
        "average_score": avg_score,
        "total_agents": len(agents),
        "agents_scored": count,
        "agents": summary
    }