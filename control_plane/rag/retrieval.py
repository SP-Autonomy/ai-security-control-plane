"""
Secure RAG retrieval with policy validation and context injection detection
Adapted from Lab 02 with defense-in-depth approach
"""

import logging
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session

from control_plane.rag.vectordb import ChromaDBManager
from control_plane.rag.validation import (
    validate_source,
    ALLOWED_SOURCES,
    check_retrieved_context,
    sanitize_html
)
from control_plane.api.models import Agent, Policy

logger = logging.getLogger(__name__)


class SecureRAGRetrieval:
    """
    Handles secure RAG retrieval with policy checks and injection detection
    
    Key security features:
    1. Source allowlist filtering
    2. Injection detection in retrieved context (Lab 02)
    3. HTML sanitization before LLM call
    4. Policy validation
    """
    
    def __init__(self):
        self.vectordb = ChromaDBManager()
        logger.info("SecureRAGRetrieval initialized")
    
    def retrieve_chunks(
        self,
        query: str,
        k: int = 3,
        source_filter: List[str] = None
    ) -> List[Dict]:
        """
        Retrieve raw chunks from vector DB
        (No security checks - use retrieve_and_validate for production)
        """
        if source_filter is None:
            source_filter = list(ALLOWED_SOURCES)
        
        chunks = self.vectordb.search(
            query=query,
            n_results=k,
            source_filter=source_filter
        )
        
        logger.info(f"Retrieved {len(chunks)} chunks for query: {query[:50]}...")
        
        return chunks
    
    def check_chunks_for_injection(
        self,
        chunks: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """
        Check retrieved chunks for injection patterns (Lab 02 defense-in-depth)
        
        This is CRITICAL: validates content at retrieval time, not just ingestion.
        Catches indirect prompt injection attacks.
        
        Returns:
            (is_safe, patterns_found)
        """
        # Concatenate all chunk content
        combined_context = "\n\n".join([c.get("text", c.get("content", "")) for c in chunks])
        
        # Check for injection
        is_safe, patterns = check_retrieved_context(combined_context)
        
        if not is_safe:
            logger.error(
                f"INJECTION DETECTED in retrieved chunks! "
                f"Found {len(patterns)} malicious patterns"
            )
        
        return is_safe, patterns
    
    def sanitize_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Sanitize chunks before LLM call (Lab 02 sanitization)
        
        Removes HTML tags and other potentially harmful content
        """
        sanitized_chunks = []
        
        for chunk in chunks:
            sanitized_chunk = chunk.copy()
            
            # Sanitize text field
            if "text" in sanitized_chunk:
                sanitized_chunk["text"] = sanitize_html(sanitized_chunk["text"])
            
            # Sanitize content field
            if "content" in sanitized_chunk:
                sanitized_chunk["content"] = sanitize_html(sanitized_chunk["content"])
            
            sanitized_chunks.append(sanitized_chunk)
        
        logger.info(f"Sanitized {len(chunks)} chunks")
        
        return sanitized_chunks
    
    def retrieve_and_validate(
        self,
        query: str,
        agent_id: int,
        k: int = 3,
        db: Session = None,
        check_injection: bool = True,
        sanitize: bool = True
    ) -> Dict:
        """
        Retrieve documents with full security validation (production mode)
        
        Args:
            query: Search query
            agent_id: Agent making the request
            k: Number of results to return
            db: Database session for policy checks
            check_injection: If True, check retrieved context for injection
            sanitize: If True, sanitize HTML before returning
        
        Returns:
            Dictionary with status and chunks
        
        Raises:
            PermissionError: If agent lacks RAG access
            ValueError: If injection detected or policy check fails
        """
        logger.info(f"RAG retrieval: query='{query[:50]}...', agent={agent_id}, k={k}")
        
        # Step 1: Check agent permissions
        if db:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                raise PermissionError(f"Agent {agent_id} not found")
            
            # Check if RAG policy is enabled
            rag_policy = db.query(Policy).filter(
                Policy.name == "RAG Context Policy"
            ).first()
            
            if rag_policy:
                if not rag_policy.enabled:
                    logger.warning(f"RAG policy disabled for agent {agent_id}")
                    return {
                        "status": "blocked",
                        "reason": "RAG policy is disabled",
                        "chunks": [],
                        "count": 0
                    }
        
        # Step 2: Retrieve chunks from vector DB
        chunks = self.retrieve_chunks(
            query=query,
            k=k,
            source_filter=list(ALLOWED_SOURCES)
        )
        
        if not chunks:
            logger.info("No chunks retrieved")
            return {
                "status": "success",
                "chunks": [],
                "count": 0,
                "message": "No relevant documents found"
            }
        
        logger.info(f"Retrieved {len(chunks)} chunks from vector DB")
        
        # Step 3: Validate each chunk's source
        validated_chunks = []
        for chunk in chunks:
            source = chunk["metadata"].get("source", "unknown")
            is_valid, _ = validate_source(source)
            
            if is_valid:
                validated_chunks.append(chunk)
            else:
                logger.warning(f"Chunk filtered (invalid source): {source}")
        
        if not validated_chunks:
            logger.warning("All chunks filtered due to invalid sources")
            return {
                "status": "blocked",
                "reason": "No chunks from allowed sources",
                "chunks": [],
                "count": 0
            }
        
        # Step 4: Check for injection in retrieved context (Lab 02 defense)
        if check_injection:
            is_safe, patterns = self.check_chunks_for_injection(validated_chunks)
            
            if not is_safe:
                logger.error(
                    f"BLOCKING request: Injection detected in retrieved chunks! "
                    f"Patterns: {patterns[:3]}"
                )
                return {
                    "status": "blocked",
                    "reason": "Injection patterns detected in retrieved content",
                    "patterns_found": patterns[:5],
                    "chunks": [],
                    "count": 0
                }
        
        # Step 5: Sanitize chunks before returning (Lab 02 sanitization)
        if sanitize:
            validated_chunks = self.sanitize_chunks(validated_chunks)
        
        logger.info(
            f"RAG retrieval complete: {len(validated_chunks)} chunks validated "
            f"(injection_check: {check_injection}, sanitized: {sanitize})"
        )
        
        return {
            "status": "success",
            "chunks": validated_chunks,
            "count": len(validated_chunks)
        }
    
    def search_by_source(
        self,
        query: str,
        source: str,
        k: int = 3
    ) -> List[Dict]:
        """Search documents from specific source"""
        logger.info(f"Searching source '{source}' with query: {query[:50]}...")
        
        is_valid, msg = validate_source(source)
        if not is_valid:
            raise ValueError(msg)
        
        return self.retrieve_chunks(
            query=query,
            k=k,
            source_filter=[source]
        )
    
    def get_context_for_prompt(
        self,
        query: str,
        agent_id: int,
        k: int = 3,
        db: Session = None,
        include_sources: bool = True
    ) -> str:
        """
        Get formatted context string for LLM prompt
        
        Returns a formatted string with sources and content,
        ready to be injected into LLM prompt
        """
        result = self.retrieve_and_validate(
            query=query,
            agent_id=agent_id,
            k=k,
            db=db
        )
        
        if result["status"] == "blocked":
            logger.warning(f"Context retrieval blocked: {result.get('reason')}")
            return ""
        
        chunks = result.get("chunks", [])
        
        if not chunks:
            return ""
        
        # Format chunks with citations (Lab 02 style)
        context_parts = []
        for i, chunk in enumerate(chunks):
            text = chunk.get("text", chunk.get("content", ""))
            source = chunk.get("source", "unknown")
            
            if include_sources:
                context_parts.append(f"[{i+1}] {text}\n(Source: {source})")
            else:
                context_parts.append(text)
        
        context = "\n\n---\n\n".join(context_parts)
        
        return context