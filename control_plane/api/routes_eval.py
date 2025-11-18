"""
Evaluation runner endpoints
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from control_plane.api.models import EvaluationResult, EvaluationResultSchema
from control_plane.api.init_db import get_db

router = APIRouter()


@router.post("/run")
async def run_evaluation(
    suite: str = Query("all", enum=["jailbreak", "exfiltration", "drift", "all"]),
    mode: str = Query("compare", enum=["compare", "policies-on", "policies-off"]),
    db: Session = Depends(get_db)
):
    """Run evaluation suite"""
    import uuid
    task_id = str(uuid.uuid4())
    
    # In production, queue this as a background task
    # For now, return task ID
    return {
        "task_id": task_id,
        "suite": suite,
        "mode": mode,
        "status": "queued"
    }


@router.get("/results", response_model=List[EvaluationResultSchema])
async def list_results(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db)
):
    """List evaluation results"""
    return (
        db.query(EvaluationResult)
        .order_by(EvaluationResult.timestamp.desc())
        .limit(limit)
        .all()
    )
