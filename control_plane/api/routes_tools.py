"""
Tool registry endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from control_plane.api.models import Tool, ToolSchema
from control_plane.api.init_db import get_db

router = APIRouter()


@router.get("/", response_model=List[ToolSchema])
async def list_tools(db: Session = Depends(get_db)):
    return db.query(Tool).all()


@router.get("/{tool_id}", response_model=ToolSchema)
async def get_tool(tool_id: int, db: Session = Depends(get_db)):
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.post("/", response_model=ToolSchema)
async def create_tool(tool: ToolSchema, db: Session = Depends(get_db)):
    db_tool = Tool(**tool.dict(exclude_unset=True))
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    return db_tool
