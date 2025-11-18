"""
Database initialization
Creates all tables and default data
FIXED: Uses correct database path
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

from control_plane.api.models import Base, Agent, Policy, Tool

# Get the control_plane directory path
CONTROL_PLANE_DIR = Path(__file__).parent.parent
DATABASE_PATH = CONTROL_PLANE_DIR / "control_plane.db"

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

print(f"Database location: {DATABASE_PATH}")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database with all tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")
    
    # Create session
    db = SessionLocal()
    
    try:
        # Check if policies exist
        policy_count = db.query(Policy).count()
        
        if policy_count == 0:
            print("Creating default policies...")
            
            policies = [
                Policy(
                    id=1,
                    name="DLP Guard",
                    version="1.0",
                    category="data_protection",
                    rego_code="package dlp\ndefault allow = true",
                    description="Redacts PII from prompts and responses",
                    enabled=True,
                    dry_run=False,
                    tags=["pii", "data-protection"]
                ),
                Policy(
                    id=2,
                    name="Tool Allowlist",
                    version="1.0",
                    category="authorization",
                    rego_code="package tools\ndefault allow = true",
                    description="Enforces tool restrictions per agent",
                    enabled=True,
                    dry_run=False,
                    tags=["tools", "authorization"]
                ),
                Policy(
                    id=3,
                    name="RAG Context Policy",
                    version="1.0",
                    category="rag",
                    rego_code="package rag\ndefault allow = true",
                    description="Controls RAG document retrieval",
                    enabled=True,
                    dry_run=False,
                    tags=["rag", "retrieval"]
                )
            ]
            
            for policy in policies:
                db.add(policy)
            
            db.commit()
            print(f"✓ Created {len(policies)} default policies")
        else:
            print(f"✓ Database already has {policy_count} policies")
        
        # Check if agents exist
        agent_count = db.query(Agent).count()
        
        if agent_count == 0:
            print("Creating default agent...")
            
            agent = Agent(
                id=1,
                name="Test Agent",
                nhi_id="nhi_test_001",
                description="Default test agent for development",
                environment="development",
                owner="test@example.com",
                allowed_tools=["web_search", "calculator"],
                budget_per_day=10000,
                memory_scope="buffer",
                status="active"
            )
            
            db.add(agent)
            db.commit()
            print("✓ Created default agent")
        else:
            print(f"✓ Database already has {agent_count} agents")
        
        # Check if tools exist
        tool_count = db.query(Tool).count()
        
        if tool_count == 0:
            print("Creating default tools...")
            
            tools = [
                Tool(
                    name="web_search",
                    description="Search the web for information",
                    category="research",
                    schema_definition={"type": "object", "properties": {"query": {"type": "string"}}},
                    timeout_seconds=30,
                    requires_approval=False,
                    risk_level="low",
                    allowed_environments=["development", "production"],
                    status="active"
                ),
                Tool(
                    name="calculator",
                    description="Perform mathematical calculations",
                    category="utility",
                    schema_definition={"type": "object", "properties": {"expression": {"type": "string"}}},
                    timeout_seconds=5,
                    requires_approval=False,
                    risk_level="low",
                    allowed_environments=["development", "production"],
                    status="active"
                ),
                Tool(
                    name="file_read",
                    description="Read file contents",
                    category="filesystem",
                    schema_definition={"type": "object", "properties": {"path": {"type": "string"}}},
                    timeout_seconds=10,
                    requires_approval=True,
                    risk_level="medium",
                    allowed_environments=["development"],
                    status="active"
                )
            ]
            
            for tool in tools:
                db.add(tool)
            
            db.commit()
            print(f"✓ Created {len(tools)} default tools")
        else:
            print(f"✓ Database already has {tool_count} tools")
        
        print(f"\n✓ Database initialization complete!")
        print(f"   Location: {DATABASE_PATH}")
        
    finally:
        db.close()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    print("Initializing database...")
    init_db()