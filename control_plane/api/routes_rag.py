"""
RAG (Retrieval-Augmented Generation) API endpoints
Integrated with Lab 02's security features and Lab 04's architecture
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging
import os

from control_plane.api.init_db import get_db
from control_plane.rag.ingestion import SecureDocumentIngestion
from control_plane.rag.retrieval import SecureRAGRetrieval

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize RAG components
doc_ingestion = SecureDocumentIngestion()
rag_retrieval = SecureRAGRetrieval()

# Test mode flag
TEST_MODE = os.getenv("RAG_TEST_MODE", "false").lower() == "true"


class DocumentUpload(BaseModel):
    content: str
    source: str
    metadata: dict = {}
    validate: bool = True


class FolderIngest(BaseModel):
    folder_path: str
    source: str
    validate: bool = True


class RAGQuery(BaseModel):
    query: str
    agent_id: int
    k: int = 3
    check_injection: bool = True
    sanitize: bool = True


class RAGAsk(BaseModel):
    """Lab 02 compatibility endpoint"""
    question: str
    user_role: str = "employee"
    agent_id: int = 1


@router.post("/documents")
async def ingest_document(doc: DocumentUpload):
    """
    Ingest a single document with security validation
    
    - Validates source against allowlist
    - Checks for injection patterns
    - Stores in ChromaDB with provenance
    """
    try:
        doc_id = doc_ingestion.ingest_document(
            content=doc.content,
            source=doc.source,
            metadata=doc.metadata,
            validate=doc.validate
        )
        
        return {
            "status": "success",
            "document_id": doc_id,
            "message": "Document ingested successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/documents/folder")
async def ingest_folder(folder: FolderIngest):
    """
    Ingest all documents from a folder
    
    - Validates each document
    - Returns statistics on success/rejection
    """
    try:
        result = doc_ingestion.ingest_folder(
            folder=folder.folder_path,
            source=folder.source,
            validate=folder.validate
        )
        
        return {
            "status": "success",
            "added": result["added"],
            "rejected": result["rejected"],
            "total": result["total"],
            "details": result["details"]
        }
    except Exception as e:
        logger.error(f"Folder ingestion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_rag(query: RAGQuery, db: Session = Depends(get_db)):
    """
    Query RAG with full security validation
    
    Security features:
    - Agent authorization
    - Policy validation
    - Injection detection in retrieved context
    - HTML sanitization
    """
    try:
        result = rag_retrieval.retrieve_and_validate(
            query=query.query,
            agent_id=query.agent_id,
            k=query.k,
            db=db,
            check_injection=query.check_injection,
            sanitize=query.sanitize
        )
        
        return result
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask")
async def ask(body: RAGAsk, db: Session = Depends(get_db)):
    """
    Lab 02 compatibility endpoint - Returns formatted answer
    
    This endpoint mimics Lab 02's /ask endpoint for testing
    """
    try:
        # Retrieve and validate chunks
        result = rag_retrieval.retrieve_and_validate(
            query=body.question,
            agent_id=body.agent_id,
            k=3,
            db=db
        )
        
        if result["status"] == "blocked":
            return {
                "blocked": True,
                "reason": result.get("reason"),
                "answer": None
            }
        
        chunks = result.get("chunks", [])
        
        if not chunks:
            return {
                "blocked": False,
                "answer": "Not found in provided context.",
                "source_ids": [],
                "chunks": []
            }
        
        # Format context (Lab 02 style)
        context_parts = []
        for i, chunk in enumerate(chunks, start=1):
            text = chunk.get("text", chunk.get("content", ""))
            source = chunk.get("source", "unknown")
            context_parts.append(f"[{i}] {text}\n(Source: {source})")
        
        context = "\n\n".join(context_parts)
        
        return {
            "blocked": False,
            "question": body.question,
            "context": context,
            "chunks": chunks,
            "source_ids": [c.get("source", "unknown") for c in chunks],
            "message": "Query successful. Use /ingress/rag on gateway for LLM answer."
        }
    
    except Exception as e:
        logger.error(f"Ask error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get RAG statistics"""
    try:
        stats = doc_ingestion.get_stats()
        return {
            "status": "success",
            **stats
        }
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document by ID"""
    try:
        doc_ingestion.vectordb.delete_document(doc_id)
        return {
            "status": "success",
            "message": f"Document {doc_id} deleted"
        }
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_collection():
    """
    Reset the entire RAG collection (use with caution!)
    Only available in test mode
    """
    if not TEST_MODE:
        raise HTTPException(
            status_code=403,
            detail="Reset only available in TEST_MODE"
        )
    
    try:
        doc_ingestion.reset_collection()
        return {
            "status": "success",
            "message": "Collection reset successfully"
        }
    except Exception as e:
        logger.error(f"Reset error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize")
async def initialize_samples():
    """
    Initialize RAG with sample documents
    
    Loads documents from:
    - data/corpus (trusted, validated)
    - data/redteam (test mode only, unvalidated)
    """
    try:
        doc_ingestion.initialize_with_samples(
            corpus_dir="data/corpus",
            redteam_dir="data/redteam"
        )
        
        stats = doc_ingestion.get_stats()
        
        return {
            "status": "success",
            "message": "RAG initialized with sample documents",
            "total_documents": stats["total_documents"],
            "sources": stats["sources"],
            "test_mode": TEST_MODE
        }
    except Exception as e:
        logger.error(f"Initialization error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        count = doc_ingestion.vectordb.count()
        return {
            "status": "healthy",
            "documents": count,
            "test_mode": TEST_MODE
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }