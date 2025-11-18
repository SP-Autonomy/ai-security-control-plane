"""
Evidence/Events API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import json
import logging

from control_plane.api.init_db import get_db
from control_plane.api.models import Event

router = APIRouter()
logger = logging.getLogger(__name__)


class EventCreate(BaseModel):
    """Event creation - accepts metadata dict and maps to individual fields"""
    event_type: str
    agent_id: Optional[int] = None
    actor: str
    trace_id: str
    metadata: dict  # We'll extract individual fields from this


class EventResponse(BaseModel):
    """Event response - reconstructs metadata dict from individual fields"""
    id: int
    event_type: str
    agent_id: Optional[int]
    actor: str
    trace_id: str
    timestamp: datetime
    metadata: dict
    
    class Config:
        from_attributes = True


def metadata_to_event_fields(metadata: dict) -> dict:
    """Extract individual fields from metadata dict"""
    return {
        "model": metadata.get("model"),
        "prompt_hash": metadata.get("prompt_hash"),
        "redactions_applied": json.dumps(metadata.get("redactions_applied", [])),
        "tool_name": metadata.get("tool_name"),
        "tool_args_hash": metadata.get("tool_args_hash"),
        "rag_chunks": json.dumps(metadata.get("rag_chunks", [])),
        "latency_ms": metadata.get("latency_ms"),
        "tokens_used": metadata.get("tokens_used"),
        "cost_usd": metadata.get("cost_usd"),
        "span_id": metadata.get("span_id"),
        "payload_json": json.dumps(metadata) if metadata else None
    }


def event_fields_to_metadata(event: Event) -> dict:
    """Reconstruct metadata dict from individual fields"""
    metadata = {}
    
    if event.model:
        metadata["model"] = event.model
    if event.prompt_hash:
        metadata["prompt_hash"] = event.prompt_hash
    if event.redactions_applied:
        try:
            metadata["redactions_applied"] = json.loads(event.redactions_applied) if isinstance(event.redactions_applied, str) else []
        except:
            metadata["redactions_applied"] = []
    if event.tool_name:
        metadata["tool_name"] = event.tool_name
    if event.tool_args_hash:
        metadata["tool_args_hash"] = event.tool_args_hash
    if event.rag_chunks:
        try:
            metadata["rag_chunks"] = json.loads(event.rag_chunks) if isinstance(event.rag_chunks, str) else []
        except:
            metadata["rag_chunks"] = []
    if event.latency_ms is not None:
        metadata["latency_ms"] = event.latency_ms
    if event.tokens_used is not None:
        metadata["tokens_used"] = event.tokens_used
    if event.cost_usd is not None:
        metadata["cost_usd"] = event.cost_usd
    if event.span_id:
        metadata["span_id"] = event.span_id
    
    # If payload_json exists, merge it
    if event.payload_json:
        try:
            payload = json.loads(event.payload_json) if isinstance(event.payload_json, str) else {}
            metadata.update(payload)
        except:
            pass
    
    return metadata


@router.post("", response_model=EventResponse, status_code=201)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    """Create a new event"""
    try:
        # Extract fields from metadata
        fields = metadata_to_event_fields(event.metadata)
        
        db_event = Event(
            event_type=event.event_type,
            agent_id=event.agent_id,
            actor=event.actor,
            trace_id=event.trace_id,
            timestamp=datetime.utcnow(),
            **fields
        )
        
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        
        # Return with reconstructed metadata
        return EventResponse(
            id=db_event.id,
            event_type=db_event.event_type,
            agent_id=db_event.agent_id,
            actor=db_event.actor,
            trace_id=db_event.trace_id,
            timestamp=db_event.timestamp,
            metadata=event_fields_to_metadata(db_event)
        )
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")


@router.get("", response_model=List[EventResponse])
def get_events(
    agent_id: Optional[int] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get events with optional filtering"""
    try:
        query = db.query(Event)
        
        if agent_id:
            query = query.filter(Event.agent_id == agent_id)
        
        if event_type:
            query = query.filter(Event.event_type == event_type)
        
        events = query.order_by(Event.timestamp.desc()).limit(limit).all()
        
        # Convert to response format
        response_events = []
        for event in events:
            response_events.append(EventResponse(
                id=event.id,
                event_type=event.event_type,
                agent_id=event.agent_id,
                actor=event.actor,
                trace_id=event.trace_id,
                timestamp=event.timestamp,
                metadata=event_fields_to_metadata(event)
            ))
        
        return response_events
    
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")


@router.get("/trace/{trace_id}", response_model=List[EventResponse])
def get_events_by_trace(trace_id: str, db: Session = Depends(get_db)):
    """Get all events for a specific trace"""
    try:
        events = db.query(Event).filter(Event.trace_id == trace_id).all()
        
        if not events:
            raise HTTPException(status_code=404, detail="No events found for trace")
        
        # Convert to response format
        response_events = []
        for event in events:
            response_events.append(EventResponse(
                id=event.id,
                event_type=event.event_type,
                agent_id=event.agent_id,
                actor=event.actor,
                trace_id=event.trace_id,
                timestamp=event.timestamp,
                metadata=event_fields_to_metadata(event)
            ))
        
        return response_events
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching events by trace: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")


@router.get("/stats")
def get_event_stats(db: Session = Depends(get_db)):
    """Get event statistics"""
    try:
        total_events = db.query(Event).count()
        
        # Events by type
        event_types = db.query(Event.event_type).distinct().all()
        by_type = {}
        for (event_type,) in event_types:
            count = db.query(Event).filter(Event.event_type == event_type).count()
            by_type[event_type] = count
        
        # Events with traces
        with_traces = db.query(Event).filter(Event.trace_id.isnot(None)).count()
        
        return {
            "total_events": total_events,
            "events_by_type": by_type,
            "events_with_traces": with_traces,
            "trace_coverage": round(with_traces / total_events * 100, 2) if total_events > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error fetching event stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@router.get("/debug")
def debug_events(db: Session = Depends(get_db)):
    """Debug endpoint to check raw event data"""
    try:
        events = db.query(Event).limit(5).all()
        debug_info = []
        
        for event in events:
            info = {
                "id": event.id,
                "event_type": event.event_type,
                "trace_id": event.trace_id,
                "model": event.model,
                "redactions": event.redactions_applied,
                "tokens": event.tokens_used,
                "latency_ms": event.latency_ms,
                "reconstructed_metadata": event_fields_to_metadata(event)
            }
            debug_info.append(info)
        
        return {
            "total_events": db.query(Event).count(),
            "sample_events": debug_info
        }
    except Exception as e:
        return {"error": str(e)}