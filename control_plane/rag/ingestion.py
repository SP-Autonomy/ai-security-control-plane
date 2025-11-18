"""
Secure document ingestion with validation
Adapted from Lab 02 with production-grade features
"""

import logging
import os
import glob
from typing import Dict, Optional, List
from datetime import datetime

from control_plane.rag.vectordb import ChromaDBManager
from control_plane.rag.validation import (
    validate_source,
    check_content_safety,
    validate_metadata,
    validate_document,
    get_trust_level
)

logger = logging.getLogger(__name__)

# Test mode flag
TEST_MODE = os.getenv("RAG_TEST_MODE", "false").lower() == "true"


class SecureDocumentIngestion:
    """Handles secure document ingestion with validation"""
    
    def __init__(self):
        self.vectordb = ChromaDBManager()
        logger.info(f"SecureDocumentIngestion initialized (TEST_MODE: {TEST_MODE})")
    
    def ingest_document(
        self,
        content: str,
        source: str,
        metadata: Dict = None,
        validate: bool = True
    ) -> str:
        """
        Ingest document with security validation
        
        Args:
            content: Document content
            source: Source identifier (must be in allowlist)
            metadata: Additional metadata
            validate: If False, skip validation (for test mode)
        
        Returns:
            document_id: Unique document identifier
        
        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Ingesting document from source: {source} (length: {len(content)}, validate: {validate})")
        
        # Step 1: Validate source
        is_valid_source, source_msg = validate_source(source)
        if not is_valid_source:
            logger.warning(f"Source validation failed: {source}")
            raise ValueError(f"Source validation failed: {source_msg}")
        
        # Step 2: Validate document content (if enabled)
        if validate:
            is_valid_doc, doc_reason = validate_document(content, source)
            if not is_valid_doc:
                logger.warning(f"Document validation failed: {doc_reason}")
                raise ValueError(f"Document validation failed: {doc_reason}")
        else:
            logger.info(f"Skipping document validation (validate=False)")
        
        # Step 3: Check content safety (if enabled)
        if validate:
            is_safe, safety_msg = check_content_safety(content)
            if not is_safe:
                logger.warning(f"Content safety check failed: {safety_msg}")
                raise ValueError(f"Content safety check failed: {safety_msg}")
        
        # Step 4: Prepare metadata
        full_metadata = {
            "source": source,
            "trust_level": get_trust_level(source),
            "ingested_at": datetime.now().isoformat(),
            "validated": validate,
            **(metadata or {})
        }
        
        # Step 5: Validate metadata
        is_valid_meta, meta_msg = validate_metadata(full_metadata)
        if not is_valid_meta:
            logger.warning(f"Metadata validation failed: {meta_msg}")
            raise ValueError(f"Metadata validation failed: {meta_msg}")
        
        # Step 6: Ingest into vector database
        try:
            doc_id = self.vectordb.add_document(
                content=content,
                source=source,
                metadata=full_metadata
            )
            
            logger.info(f"Document ingested successfully: {doc_id}")
            
            return doc_id
        
        except Exception as e:
            logger.error(f"Ingestion failed: {str(e)}")
            raise
    
    def ingest_file(
        self,
        filepath: str,
        source: str,
        validate: bool = True
    ) -> str:
        """Ingest document from file"""
        logger.info(f"Ingesting file: {filepath}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file: {str(e)}")
            raise ValueError(f"Failed to read file: {str(e)}")
        
        metadata = {
            "filename": os.path.basename(filepath),
            "filepath": filepath
        }
        
        return self.ingest_document(content, source, metadata, validate=validate)
    
    def ingest_folder(
        self,
        folder: str,
        source: str,
        validate: bool = True,
        extensions: List[str] = None
    ) -> Dict:
        """
        Ingest all documents from a folder (Lab 02 compatibility)
        
        Args:
            folder: Path to folder containing documents
            source: Source identifier for all documents
            validate: If True, validate documents before ingestion
            extensions: List of file extensions to include (default: ['.md', '.txt'])
        
        Returns:
            Dictionary with ingestion statistics
        """
        if extensions is None:
            extensions = ['.md', '.txt']
        
        logger.info(f"Ingesting folder: {folder} (source: {source}, validate: {validate})")
        
        # Find all matching files
        paths = []
        for ext in extensions:
            paths.extend(sorted(glob.glob(os.path.join(folder, f"*{ext}"))))
        
        if not paths:
            logger.warning(f"No documents found in {folder}")
            return {
                "added": 0,
                "rejected": 0,
                "total": 0,
                "details": []
            }
        
        added = 0
        rejected = []
        details = []
        
        for p in paths:
            try:
                doc_id = self.ingest_file(p, source, validate=validate)
                added += 1
                details.append({
                    "file": p,
                    "status": "success",
                    "document_id": doc_id
                })
            except ValueError as e:
                # Validation failed
                rejected.append((p, str(e)))
                details.append({
                    "file": p,
                    "status": "rejected",
                    "reason": str(e)
                })
                logger.warning(f"Rejected: {p} ({str(e)})")
            except Exception as e:
                # Other error
                rejected.append((p, str(e)))
                details.append({
                    "file": p,
                    "status": "error",
                    "reason": str(e)
                })
                logger.error(f"Error processing {p}: {e}")
        
        result = {
            "added": added,
            "rejected": len(rejected),
            "total": len(paths),
            "details": details
        }
        
        logger.info(
            f"Folder ingestion complete: {added}/{len(paths)} added, "
            f"{len(rejected)} rejected"
        )
        
        return result
    
    def batch_ingest(
        self,
        documents: List[Dict],
        source: str,
        validate: bool = True
    ) -> List[Dict]:
        """
        Ingest multiple documents at once
        
        Args:
            documents: List of dicts with 'content' and optional 'metadata'
            source: Source identifier
            validate: If True, validate each document
        
        Returns:
            List of results for each document
        """
        logger.info(f"Batch ingesting {len(documents)} documents from {source}")
        
        results = []
        for i, doc in enumerate(documents):
            try:
                doc_id = self.ingest_document(
                    content=doc.get("content"),
                    source=source,
                    metadata=doc.get("metadata", {}),
                    validate=validate
                )
                results.append({
                    "index": i,
                    "status": "success",
                    "document_id": doc_id
                })
            except Exception as e:
                logger.error(f"Failed to ingest document {i}: {str(e)}")
                results.append({
                    "index": i,
                    "status": "failed",
                    "error": str(e)
                })
        
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(f"Batch ingestion complete: {success_count}/{len(documents)} succeeded")
        
        return results
    
    def reset_collection(self):
        """Reset the entire collection (use with caution)"""
        logger.warning("Resetting collection...")
        self.vectordb.reset()
        logger.info("Collection reset complete")
    
    def get_stats(self) -> Dict:
        """Get ingestion statistics"""
        return {
            "total_documents": self.vectordb.count(),
            "sources": self.vectordb.list_sources(),
            "test_mode": TEST_MODE
        }
    
    def initialize_with_samples(
        self,
        corpus_dir: str = "data/corpus",
        redteam_dir: str = "data/redteam"
    ):
        """
        Initialize RAG with sample documents (Lab 02 startup logic)
        
        Args:
            corpus_dir: Path to trusted documents
            redteam_dir: Path to red team test documents
        """
        logger.info("Initializing RAG with sample documents...")
        
        # Reset collection
        self.reset_collection()
        
        # Ingest trusted corpus (with validation)
        if os.path.exists(corpus_dir):
            result = self.ingest_folder(corpus_dir, "internal_docs", validate=True)
            logger.info(
                f"Ingested {result['added']} trusted docs from {corpus_dir} "
                f"({result['rejected']} rejected)"
            )
        else:
            logger.warning(f"Corpus directory not found: {corpus_dir}")
        
        # In test mode, ingest red team docs WITHOUT validation
        if TEST_MODE and os.path.exists(redteam_dir):
            logger.warning(f"🔴 TEST MODE: Including red team documents")
            result = self.ingest_folder(redteam_dir, "redteam", validate=False)
            logger.warning(
                f"🔴 TEST MODE: Ingested {result['added']} red team docs (unvalidated)"
            )
        
        stats = self.get_stats()
        logger.info(f"Initialization complete. Total documents: {stats['total_documents']}")