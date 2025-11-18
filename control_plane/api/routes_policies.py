"""
Policy Management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from control_plane.api.init_db import get_db
from control_plane.api.models import Policy, PolicySchema

router = APIRouter()


class PolicyCreate(BaseModel):
    name: str
    version: str
    category: Optional[str] = None
    rego_code: str
    description: Optional[str] = None
    enabled: bool = True
    dry_run: bool = False
    tags: List[str] = []


class PolicyUpdate(BaseModel):
    version: Optional[str] = None
    rego_code: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    dry_run: Optional[bool] = None
    tags: Optional[List[str]] = None


@router.post("", response_model=PolicySchema, status_code=201)
def create_policy(policy: PolicyCreate, db: Session = Depends(get_db)):
    """Create a new policy"""
    
    # Check if policy name+version exists
    existing = db.query(Policy).filter(
        Policy.name == policy.name,
        Policy.version == policy.version
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Policy {policy.name} version {policy.version} already exists"
        )
    
    db_policy = Policy(
        name=policy.name,
        version=policy.version,
        category=policy.category,
        rego_code=policy.rego_code,
        description=policy.description,
        enabled=policy.enabled,
        dry_run=policy.dry_run,
        tags=policy.tags
    )
    
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    
    return PolicySchema.from_orm(db_policy)


@router.get("", response_model=List[PolicySchema])
def list_policies(
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all policies with optional filtering"""
    
    query = db.query(Policy)
    
    if category:
        query = query.filter(Policy.category == category)
    
    if enabled is not None:
        query = query.filter(Policy.enabled == enabled)
    
    policies = query.all()
    return [PolicySchema.from_orm(policy) for policy in policies]


@router.get("/{policy_id}", response_model=PolicySchema)
def get_policy(policy_id: int, db: Session = Depends(get_db)):
    """Get policy by ID"""
    
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return PolicySchema.from_orm(policy)


@router.get("/name/{policy_name}", response_model=List[PolicySchema])
def get_policy_by_name(policy_name: str, db: Session = Depends(get_db)):
    """Get all versions of a policy by name"""
    
    policies = db.query(Policy).filter(Policy.name == policy_name).all()
    
    if not policies:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return [PolicySchema.from_orm(policy) for policy in policies]


@router.patch("/{policy_id}", response_model=PolicySchema)
def update_policy(policy_id: int, update: PolicyUpdate, db: Session = Depends(get_db)):
    """Update policy"""
    
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    if update.version is not None:
        policy.version = update.version
    if update.rego_code is not None:
        policy.rego_code = update.rego_code
    if update.description is not None:
        policy.description = update.description
    if update.enabled is not None:
        policy.enabled = update.enabled
    if update.dry_run is not None:
        policy.dry_run = update.dry_run
    if update.tags is not None:
        policy.tags = update.tags
    
    policy.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(policy)
    
    return PolicySchema.from_orm(policy)


@router.patch("/{policy_id}/enable")
def enable_policy(policy_id: int, db: Session = Depends(get_db)):
    """Enable a policy"""
    
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    policy.enabled = True
    policy.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "success", "message": f"Policy {policy_id} enabled"}


@router.patch("/{policy_id}/disable")
def disable_policy(policy_id: int, db: Session = Depends(get_db)):
    """Disable a policy"""
    
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    policy.enabled = False
    policy.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "success", "message": f"Policy {policy_id} disabled"}


@router.patch("/{policy_id}/dry-run")
def toggle_dry_run(policy_id: int, enabled: bool, db: Session = Depends(get_db)):
    """Toggle dry run mode"""
    
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    policy.dry_run = enabled
    policy.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "success", "message": f"Policy {policy_id} dry_run = {enabled}"}


@router.delete("/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    """Delete a policy"""
    
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    db.delete(policy)
    db.commit()
    
    return {"status": "success", "message": f"Policy {policy_id} deleted"}


@router.get("/{policy_id}/stats")
def get_policy_stats(policy_id: int, db: Session = Depends(get_db)):
    """Get policy statistics"""
    
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    # Decision stats
    from control_plane.api.models import Decision
    total_decisions = db.query(Decision).filter(Decision.policy_id == policy_id).count()
    
    allowed = db.query(Decision).filter(
        Decision.policy_id == policy_id,
        Decision.outcome == "allow"
    ).count()
    
    denied = db.query(Decision).filter(
        Decision.policy_id == policy_id,
        Decision.outcome == "deny"
    ).count()
    
    return {
        "policy_id": policy_id,
        "policy_name": policy.name,
        "version": policy.version,
        "enabled": policy.enabled,
        "dry_run": policy.dry_run,
        "total_decisions": total_decisions,
        "allowed": allowed,
        "denied": denied,
        "deny_rate": round(denied / total_decisions * 100, 2) if total_decisions > 0 else 0
    }