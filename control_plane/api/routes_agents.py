"""
Agent Registry API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from control_plane.api.init_db import get_db
from control_plane.api.models import Agent, AgentSchema

router = APIRouter()


class AgentCreate(BaseModel):
    name: str
    nhi_id: Optional[str] = None
    description: Optional[str] = None
    environment: str = "development"
    owner: Optional[str] = None
    allowed_tools: List[str] = []
    budget_per_day: int = 100
    memory_scope: str = "buffer"
    status: str = "active"


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    environment: Optional[str] = None
    owner: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    budget_per_day: Optional[int] = None
    status: Optional[str] = None


@router.post("", response_model=AgentSchema, status_code=201)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    """Register a new agent"""
    
    # Check if name exists
    existing = db.query(Agent).filter(Agent.name == agent.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agent name already exists")
    
    # Check if NHI ID exists
    if agent.nhi_id:
        existing_nhi = db.query(Agent).filter(Agent.nhi_id == agent.nhi_id).first()
        if existing_nhi:
            raise HTTPException(status_code=400, detail="NHI ID already exists")
    
    # Create agent
    db_agent = Agent(
        name=agent.name,
        nhi_id=agent.nhi_id,
        description=agent.description,
        environment=agent.environment,
        owner=agent.owner,
        allowed_tools=agent.allowed_tools,
        budget_per_day=agent.budget_per_day,
        memory_scope=agent.memory_scope,
        status=agent.status
    )
    
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    
    return AgentSchema.from_orm(db_agent)


@router.get("", response_model=List[AgentSchema])
def list_agents(
    environment: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all agents with optional filtering"""
    
    query = db.query(Agent)
    
    if environment:
        query = query.filter(Agent.environment == environment)
    
    if status:
        query = query.filter(Agent.status == status)
    
    agents = query.all()
    return [AgentSchema.from_orm(agent) for agent in agents]


@router.get("/{agent_id}", response_model=AgentSchema)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    """Get agent by ID"""
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentSchema.from_orm(agent)


@router.get("/nhi/{nhi_id}", response_model=AgentSchema)
def get_agent_by_nhi(nhi_id: str, db: Session = Depends(get_db)):
    """Get agent by NHI ID"""
    
    agent = db.query(Agent).filter(Agent.nhi_id == nhi_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentSchema.from_orm(agent)


@router.patch("/{agent_id}", response_model=AgentSchema)
def update_agent(agent_id: int, update: AgentUpdate, db: Session = Depends(get_db)):
    """Update agent"""
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Update fields
    if update.name is not None:
        agent.name = update.name
    if update.description is not None:
        agent.description = update.description
    if update.environment is not None:
        agent.environment = update.environment
    if update.owner is not None:
        agent.owner = update.owner
    if update.allowed_tools is not None:
        agent.allowed_tools = update.allowed_tools
    if update.budget_per_day is not None:
        agent.budget_per_day = update.budget_per_day
    if update.status is not None:
        agent.status = update.status
    
    db.commit()
    db.refresh(agent)
    
    return AgentSchema.from_orm(agent)


@router.patch("/{agent_id}/activate")
def activate_agent(agent_id: int, db: Session = Depends(get_db)):
    """Activate an agent"""
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.status = "active"
    db.commit()
    
    return {"status": "success", "message": f"Agent {agent_id} activated"}


@router.patch("/{agent_id}/deactivate")
def deactivate_agent(agent_id: int, db: Session = Depends(get_db)):
    """Deactivate an agent"""
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.status = "inactive"
    db.commit()
    
    return {"status": "success", "message": f"Agent {agent_id} deactivated"}


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    """Delete an agent"""
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    db.delete(agent)
    db.commit()
    
    return {"status": "success", "message": f"Agent {agent_id} deleted"}


@router.get("/{agent_id}/stats")
def get_agent_stats(agent_id: int, db: Session = Depends(get_db)):
    """Get agent statistics"""
    
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Event stats
    from control_plane.api.models import Event
    total_events = db.query(Event).filter(Event.agent_id == agent_id).count()
    
    # RAG events
    rag_events = db.query(Event).filter(
        Event.agent_id == agent_id,
        Event.event_type.like("%rag%")
    ).count()
    
    # Token usage
    token_sum = db.query(Event.tokens_used).filter(
        Event.agent_id == agent_id,
        Event.tokens_used.isnot(None)
    ).all()
    total_tokens = sum([t[0] for t in token_sum if t[0]])
    
    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "total_events": total_events,
        "rag_requests": rag_events,
        "total_tokens_used": total_tokens,
        "budget_per_day": agent.budget_per_day,
        "budget_remaining": max(0, agent.budget_per_day - total_tokens),
        "status": agent.status
    }