"""
Database models for AI Security Control Plane
Aligned with NIST AI RMF and OWASP Agentic SecOps
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

Base = declarative_base()

# =============================================================================
# AGENT REGISTRY (NIST: Govern/Map)
# =============================================================================

class Agent(Base):
    """Agent registry with NHI credentials"""
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    nhi_id = Column(String, unique=True, index=True)
    description = Column(Text)
    environment = Column(String, default="development")
    owner = Column(String)
    allowed_tools = Column(JSON, default=list)
    budget_per_day = Column(Integer, default=100)
    memory_scope = Column(String, default="buffer")
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    events = relationship("Event", back_populates="agent")
    posture_scores = relationship("PostureScore", back_populates="agent")


class AgentSchema(BaseModel):
    """Pydantic schema for Agent"""
    id: Optional[int] = None
    name: str
    nhi_id: Optional[str] = None
    description: Optional[str] = None
    environment: str = "development"
    owner: Optional[str] = None
    allowed_tools: List[str] = Field(default_factory=list)
    budget_per_day: int = 100
    memory_scope: str = "buffer"
    status: str = "active"
    
    class Config:
        from_attributes = True


# =============================================================================
# TOOL REGISTRY (OWASP: Tool Scopes)
# =============================================================================

class Tool(Base):
    """Tool registry with schemas and budgets"""
    __tablename__ = "tools"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text)
    category = Column(String)
    schema_definition = Column(JSON)  # Renamed from schema_json to avoid Pydantic conflict
    timeout_seconds = Column(Integer, default=30)
    requires_approval = Column(Boolean, default=False)
    risk_level = Column(String, default="low")
    allowed_environments = Column(JSON, default=list)
    mcp_endpoint = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ToolSchema(BaseModel):
    """Pydantic schema for Tool"""
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    schema_definition: Optional[Dict[str, Any]] = None  # Renamed from schema_json
    timeout_seconds: int = 30
    requires_approval: bool = False
    risk_level: str = "low"
    allowed_environments: List[str] = Field(default_factory=list)
    mcp_endpoint: Optional[str] = None
    status: str = "active"
    
    class Config:
        from_attributes = True


# =============================================================================
# POLICY STORE
# =============================================================================

class Policy(Base):
    """Policy-as-code with Rego bundles"""
    __tablename__ = "policies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    category = Column(String)
    rego_code = Column(Text, nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    dry_run = Column(Boolean, default=False)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    decisions = relationship("Decision", back_populates="policy")


class PolicySchema(BaseModel):
    """Pydantic schema for Policy"""
    id: Optional[int] = None
    name: str
    version: str
    category: Optional[str] = None
    rego_code: str
    description: Optional[str] = None
    enabled: bool = True
    dry_run: bool = False
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


# =============================================================================
# EVENT LOG (OWASP: Agent Activity Monitoring)
# =============================================================================

class Event(Base):
    """Immutable event log for all operations"""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    event_type = Column(String, index=True)
    actor = Column(String)
    model = Column(String, nullable=True)
    prompt_hash = Column(String, nullable=True)
    redactions_applied = Column(JSON, default=list)
    tool_name = Column(String, nullable=True)
    tool_args_hash = Column(String, nullable=True)
    rag_chunks = Column(JSON, default=list)
    latency_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    trace_id = Column(String, index=True)
    span_id = Column(String)
    payload_json = Column(JSON)
    
    agent = relationship("Agent", back_populates="events")


class EventSchema(BaseModel):
    """Pydantic schema for Event"""
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_id: Optional[int] = None
    event_type: str
    actor: str
    model: Optional[str] = None
    prompt_hash: Optional[str] = None
    redactions_applied: List[str] = Field(default_factory=list)
    tool_name: Optional[str] = None
    tool_args_hash: Optional[str] = None
    rag_chunks: List[Dict[str, str]] = Field(default_factory=list)
    latency_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    payload_json: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


# =============================================================================
# DECISION LOG (OWASP: Audit Trail)
# =============================================================================

class Decision(Base):
    """Policy decision log"""
    __tablename__ = "decisions"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    policy_id = Column(Integer, ForeignKey("policies.id"))
    policy_name = Column(String, index=True)
    policy_version = Column(String)
    outcome = Column(String)
    reasons = Column(JSON, default=list)
    input_hash = Column(String)
    context = Column(JSON)
    trace_id = Column(String, index=True)
    
    policy = relationship("Policy", back_populates="decisions")


class DecisionSchema(BaseModel):
    """Pydantic schema for Decision"""
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    policy_id: Optional[int] = None
    policy_name: str
    policy_version: str
    outcome: str
    reasons: List[str] = Field(default_factory=list)
    input_hash: str
    context: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None
    
    class Config:
        from_attributes = True


# =============================================================================
# POSTURE SCORES (OWASP: Secure Posture Management)
# =============================================================================

class PostureScore(Base):
    """Continuous posture scoring"""
    __tablename__ = "posture_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    overall_score = Column(Integer)
    registry_score = Column(Integer)
    tools_score = Column(Integer)
    tracing_score = Column(Integer)
    dlp_score = Column(Integer)
    policy_score = Column(Integer)
    failing_checks = Column(JSON, default=list)
    recommendations = Column(JSON, default=list)
    
    agent = relationship("Agent", back_populates="posture_scores")


class PostureScoreSchema(BaseModel):
    """Pydantic schema for PostureScore"""
    id: Optional[int] = None
    agent_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    overall_score: int
    registry_score: int
    tools_score: int
    tracing_score: int
    dlp_score: int
    policy_score: int
    failing_checks: List[str] = Field(default_factory=list)
    recommendations: List[Dict[str, str]] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


# =============================================================================
# EVALUATION RESULTS
# =============================================================================

class EvaluationResult(Base):
    """Security evaluation results"""
    __tablename__ = "evaluation_results"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    suite_name = Column(String, index=True)
    test_name = Column(String)
    mode = Column(String)
    passed = Column(Boolean)
    details = Column(JSON)
    evidence_links = Column(JSON, default=list)
    delta_comparison = Column(JSON, nullable=True)


class EvaluationResultSchema(BaseModel):
    """Pydantic schema for EvaluationResult"""
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    suite_name: str
    test_name: str
    mode: str
    passed: bool
    details: Optional[Dict[str, Any]] = None
    evidence_links: List[str] = Field(default_factory=list)
    delta_comparison: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True