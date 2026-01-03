"""
PineconeVectorDBStorage - Custom LightRAG storage backend for Pinecone.

Maps LightRAG domains (entities, relationships, chunks) to Pinecone namespaces.
This enables the hybrid GraphRAG architecture using Pinecone's serverless infrastructure.
"""

import os
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np

try:
    from lightrag.base import BaseVectorStorage
except ImportError:
    # Fallback for development/testing
    class BaseVectorStorage:
        def __init__(self, global_config: Dict[str, Any], **kwargs):
            self.global_config = global_config

from pinecone import Pinecone


@dataclass
class PineconeVectorDBStorage(BaseVectorStorage):
    """
    Vector storage implementation using Pinecone.
    
    Separates different types of LightRAG vectors into Pinecone namespaces:
    - entities: Extracted entity descriptions
    - relationships: Relationship descriptions between entities
    - chunks: Original text chunks
    
    This separation allows for targeted retrieval in different search modes.
    """
    
    namespace: str = field(default="default")
    max_batch_size: int = field(default=100)
    index: Any = field(default=None, init=False)
    
    def __post_init__(self):
        """Initialize Pinecone connection after dataclass initialization."""
        api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME", "liquid-graph")
        
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required")
        
        # Get namespace from kwargs if provided during instantiation
        if hasattr(self, '_init_kwargs') and 'namespace' in self._init_kwargs:
            self.namespace = self._init_kwargs['namespace']
        
        pc = Pinecone(api_key=api_key)
        self.index = pc.Index(index_name)
        
        print(f"[PineconeStorage] Connected to index '{index_name}', namespace '{self.namespace}'")
    
    def __init__(self, global_config: Dict[str, Any], **kwargs):
        """
        Initialize the Pinecone storage.
        
        Args:
            global_config: LightRAG global configuration dict
            **kwargs: Additional config including 'namespace' for Pinecone namespace
        """
        # Store kwargs for post_init access
        self._init_kwargs = kwargs
        self.namespace = kwargs.get("namespace", "default")
        
        # Call parent init
        super().__init__(global_config, **kwargs)
        
        # Now do Pinecone-specific init
        api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME", "liquid-graph")
        
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required")
        
        pc = Pinecone(api_key=api_key)
        self.index = pc.Index(index_name)
        self.max_batch_size = 100
        
        print(f"[PineconeStorage] Connected to index '{index_name}', namespace '{self.namespace}'")

    async def upsert(self, data: Dict[str, Dict[str, Any]]) -> None:
        """
        Batch upsert vectors to Pinecone.
        
        LightRAG sends data as: {id: {"vector": [...], "content": "...", "meta": {...}}}
        We store content in metadata for later retrieval without secondary DB.
        
        Args:
            data: Dictionary mapping IDs to vector data
        """
        vectors = []
        
        for id_key, doc in data.items():
            # Flatten content into metadata for direct retrieval
            meta = doc.get("meta", {}).copy()
            content = doc.get("content", "")
            
            # Truncate content if too long for Pinecone metadata (40KB limit)
            if len(content) > 30000:
                content = content[:30000] + "...[truncated]"
            
            meta["__content__"] = content
            
            vector_data = doc.get("vector", [])
            if not vector_data:
                continue
                
            vectors.append({
                "id": str(id_key),
                "values": vector_data if isinstance(vector_data, list) else vector_data.tolist(),
                "metadata": meta
            })
            
            # Send in batches to respect API limits
            if len(vectors) >= self.max_batch_size:
                await self._upsert_batch(vectors)
                vectors = []
        
        # Upload any remaining vectors
        if vectors:
            await self._upsert_batch(vectors)
    
    async def _upsert_batch(self, vectors: List[Dict]) -> None:
        """Helper to upsert a batch of vectors."""
        try:
            # Pinecone client is sync, run in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.index.upsert(vectors=vectors, namespace=self.namespace)
            )
            print(f"[PineconeStorage] Upserted {len(vectors)} vectors to '{self.namespace}'")
        except Exception as e:
            print(f"[PineconeStorage] Error upserting to '{self.namespace}': {e}")
            raise

    async def query(self, query: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Query vectors from Pinecone.
        
        Args:
            query: Query vector as numpy array
            top_k: Number of results to return
            
        Returns:
            List of result dicts with id, vector, score, content, and meta
        """
        # Convert numpy array to list for Pinecone
        if isinstance(query, np.ndarray):
            query_vector = query.tolist()
        else:
            query_vector = query
        
        try:
            # Run sync Pinecone query in executor
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.index.query(
                    vector=query_vector,
                    top_k=top_k,
                    namespace=self.namespace,
                    include_metadata=True,
                    include_values=True
                )
            )
            
            # Transform results to LightRAG expected format
            output = []
            for match in results.get("matches", []):
                metadata = match.get("metadata", {})
                output.append({
                    "id": match["id"],
                    "vector": match.get("values", []),
                    "score": match.get("score", 0.0),
                    "content": metadata.pop("__content__", ""),
                    "meta": metadata
                })
            
            return output
            
        except Exception as e:
            print(f"[PineconeStorage] Error querying '{self.namespace}': {e}")
            return []

    async def delete(self, ids: List[str]) -> None:
        """
        Delete vectors by ID.
        
        Args:
            ids: List of vector IDs to delete
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.index.delete(ids=ids, namespace=self.namespace)
            )
            print(f"[PineconeStorage] Deleted {len(ids)} vectors from '{self.namespace}'")
        except Exception as e:
            print(f"[PineconeStorage] Error deleting from '{self.namespace}': {e}")


# Factory function for LightRAG integration
def create_pinecone_storage(namespace: str):
    """
    Factory function to create namespace-specific storage instances.
    
    Args:
        namespace: Pinecone namespace for this storage instance
        
    Returns:
        Configured PineconeVectorDBStorage instance
    """
    def factory(global_config: Dict[str, Any], **kwargs) -> PineconeVectorDBStorage:
        return PineconeVectorDBStorage(global_config, namespace=namespace, **kwargs)
    return factory
