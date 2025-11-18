"""
ChromaDB Vector Database Manager for Secure RAG
Adapted from Lab 02 with Ollama embeddings
"""

import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Optional
import hashlib
from datetime import datetime
import logging
import requests

logger = logging.getLogger(__name__)


class ChromaDBManager:
    """Manages ChromaDB for secure document storage and retrieval"""
    
    def __init__(self, persist_directory: str = None):
        if persist_directory is None:
            # Default to data/chroma_db in project root
            persist_directory = os.path.join(
                os.path.dirname(__file__),
                "../../data/chroma_db"
            )
        
        # Ensure directory exists
        os.makedirs(persist_directory, exist_ok=True)
        
        logger.info(f"Initializing ChromaDB at: {persist_directory}")
        
        # Initialize ChromaDB client (matching Lab 02 config)
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Collection name from env or default
        self.collection_name = os.getenv("RAG_COLLECTION", "lab04_secure_docs")
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Secure document storage with provenance"}
        )
        
        # Ollama config for embeddings
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        
        logger.info(f"ChromaDB initialized. Documents: {self.count()}")
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding from Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": self.embed_model,
                    "prompt": text
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()["embedding"]
            else:
                logger.error(f"Ollama embedding failed: {response.status_code}")
                raise Exception(f"Embedding failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            # Fallback: use ChromaDB's default embedding function
            return None
    
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts"""
        embeddings = []
        for text in texts:
            emb = self._get_embedding(text)
            if emb:
                embeddings.append(emb)
            else:
                # ChromaDB will use its default if None
                return None
        return embeddings
    
    def add_document(
        self,
        content: str,
        source: str,
        metadata: Dict = None
    ) -> str:
        """Add document with security metadata"""
        
        # Generate unique document ID
        doc_id = hashlib.sha256(
            f"{content}{source}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Prepare metadata (matching Lab 02 structure)
        doc_metadata = {
            "source": source,
            "source_path": metadata.get("filepath", f"{source}/{doc_id}"),
            "trust_level": metadata.get("trust_level", "internal"),
            "ingested_at": datetime.now().isoformat(),
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "length": len(content),
            **(metadata or {})
        }
        
        # Get embedding
        try:
            embedding = self._get_embedding(content)
            
            if embedding:
                # Add with custom embedding
                self.collection.add(
                    documents=[content],
                    metadatas=[doc_metadata],
                    embeddings=[embedding],
                    ids=[doc_id]
                )
            else:
                # Let ChromaDB generate embedding
                self.collection.add(
                    documents=[content],
                    metadatas=[doc_metadata],
                    ids=[doc_id]
                )
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            # Fallback to ChromaDB's default embedding
            self.collection.add(
                documents=[content],
                metadatas=[doc_metadata],
                ids=[doc_id]
            )
        
        logger.info(f"Document added: {doc_id} (source: {source}, length: {len(content)})")
        
        return doc_id
    
    def search(
        self,
        query: str,
        n_results: int = 3,
        source_filter: List[str] = None
    ) -> List[Dict]:
        """
        Search documents with optional source filtering
        Matches Lab 02's query() function signature
        """
        
        # Build where clause for source filtering
        where = None
        if source_filter:
            where = {"source": {"$in": source_filter}}
        
        # Get query embedding
        try:
            query_embedding = self._get_embedding(query)
            
            if query_embedding:
                # Query with custom embedding
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where,
                    include=["documents", "metadatas", "distances"]
                )
            else:
                # Let ChromaDB handle embedding
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where,
                    include=["documents", "metadatas", "distances"]
                )
        except Exception as e:
            logger.error(f"Error during search: {e}")
            # Fallback to text-based query
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
        
        # Format results (matching Lab 02 structure)
        hits = []
        if results and results["documents"] and len(results["documents"]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                hits.append({
                    "id": results["ids"][0][i],
                    "text": doc,  # Lab 02 uses "text" not "content"
                    "content": doc,  # Also provide "content" for Lab 04 compatibility
                    "source": results["metadatas"][0][i].get("source_path", "unknown"),
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i]
                })
        
        logger.info(f"Search completed: {len(hits)} results for query: {query[:50]}...")
        
        return hits
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get document by ID"""
        result = self.collection.get(ids=[doc_id], include=["documents", "metadatas"])
        
        if result and result["documents"]:
            return {
                "id": doc_id,
                "content": result["documents"][0],
                "text": result["documents"][0],
                "metadata": result["metadatas"][0]
            }
        return None
    
    def delete_document(self, doc_id: str):
        """Delete document by ID"""
        self.collection.delete(ids=[doc_id])
        logger.info(f"Document deleted: {doc_id}")
    
    def reset(self):
        """Reset collection (use with caution)"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Secure document storage with provenance"}
        )
        logger.warning("Collection reset")
    
    def count(self) -> int:
        """Get total document count"""
        return self.collection.count()
    
    def list_sources(self) -> List[str]:
        """List all unique sources"""
        all_docs = self.collection.get(include=["metadatas"])
        sources = set()
        if all_docs and all_docs["metadatas"]:
            for metadata in all_docs["metadatas"]:
                sources.add(metadata.get("source", "unknown"))
        return list(sources)
    
    def add_docs_from_folder(
        self,
        folder: str,
        source: str,
        validate: bool = True
    ) -> int:
        """
        Add documents from folder (Lab 02 compatibility)
        
        Args:
            folder: Path to folder containing documents
            source: Source identifier for all documents
            validate: If True, validate documents before ingestion
        
        Returns:
            Number of documents successfully added
        """
        import glob
        from control_plane.rag.validation import validate_document
        
        paths = sorted(glob.glob(os.path.join(folder, "*.md"))) + \
                sorted(glob.glob(os.path.join(folder, "*.txt")))
        
        if not paths:
            logger.warning(f"No documents found in {folder}")
            return 0
        
        added = 0
        rejected = []
        
        for p in paths:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Validate if enabled
                if validate:
                    is_valid, reason = validate_document(content, source)
                    if not is_valid:
                        rejected.append((p, reason))
                        logger.warning(f"Rejected: {p} ({reason})")
                        continue
                
                # Add document
                self.add_document(
                    content=content,
                    source=source,
                    metadata={
                        "filename": os.path.basename(p),
                        "filepath": p,
                        "trust_level": "redteam" if source == "redteam" else "internal"
                    }
                )
                added += 1
            
            except Exception as e:
                logger.error(f"Error processing {p}: {e}")
                rejected.append((p, str(e)))
        
        if rejected:
            logger.warning(f"Total rejected: {len(rejected)} documents")
        
        logger.info(f"Added {added} documents from {folder}")
        
        return added