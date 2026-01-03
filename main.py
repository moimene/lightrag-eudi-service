"""
LightRAG EUDI Wallet Knowledge Graph Service

FastAPI server for ingesting documents into a LightRAG Knowledge Graph.
Uses background tasks to avoid timeout issues with n8n webhook calls.

The graph topology is persisted to a Railway Volume at /app/data.
Vectors are stored in Pinecone using namespace separation.
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# =============================================================================
# Configuration
# =============================================================================

# Persistent working directory for graph topology
# On Railway, this MUST be a mounted volume to survive deploys
WORKDIR = os.getenv("LIGHTRAG_WORKDIR", "/app/data")

# Ensure working directory exists
os.makedirs(WORKDIR, exist_ok=True)

# Pinecone namespace configuration
NAMESPACE_ENTITIES = os.getenv("PINECONE_NS_ENTITIES", "liquid_entities")
NAMESPACE_RELATIONS = os.getenv("PINECONE_NS_RELATIONS", "liquid_relations")
NAMESPACE_CHUNKS = os.getenv("PINECONE_NS_CHUNKS", "liquid_chunks")

# =============================================================================
# LightRAG Import (with graceful fallback)
# =============================================================================

LIGHTRAG_AVAILABLE = False
LightRAG = None
llm_model_func = None
embedding_func = None

try:
    from lightrag import LightRAG as LR, EmbeddingFunc
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed
    import numpy as np
    
    LightRAG = LR
    
    # Create async LLM function for OpenAI
    async def llm_func(
        prompt, system_prompt=None, history_messages=[], 
        keyword_extraction=False, **kwargs
    ) -> str:
        return await openai_complete_if_cache(
            "gpt-4o-mini",
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=os.getenv("OPENAI_API_KEY"),
            **kwargs
        )
    
    # Create embedding function wrapper
    async def embed_texts(texts: list) -> np.ndarray:
        return await openai_embed(
            texts,
            model="text-embedding-3-small",
            api_key=os.getenv("OPENAI_API_KEY")
        )
    
    llm_model_func = llm_func
    embedding_func = EmbeddingFunc(
        embedding_dim=1536,
        max_token_size=8192,
        func=embed_texts
    )
    
    LIGHTRAG_AVAILABLE = True
    print("[INFO] LightRAG imported successfully")
except ImportError as e:
    print(f"[WARNING] LightRAG import failed: {e}")
    print("[INFO] Service will run in degraded mode (health checks only)")
except Exception as e:
    print(f"[ERROR] Unexpected error importing LightRAG: {e}")
    import traceback
    traceback.print_exc()


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="LightRAG EUDI Knowledge Graph",
    description="Knowledge Graph ingestion service for EUDI Wallet documentation",
    version="1.0.0"
)

# CORS configuration for n8n and other callers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# LightRAG Instance (Lazy Singleton)
# =============================================================================

_rag_instance: Optional[Any] = None


def get_rag_instance():
    """
    Get or create the singleton LightRAG instance.
    
    Uses gpt-4o-mini for economic indexing (entity/relation extraction).
    Graph topology is saved locally in WORKDIR.
    """
    global _rag_instance
    
    if _rag_instance is not None:
        return _rag_instance
    
    if not LIGHTRAG_AVAILABLE or LightRAG is None:
        print("[ERROR] Cannot create RAG instance - LightRAG not available")
        return None
    
    # Verify required environment variables
    required_vars = ["OPENAI_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"[ERROR] Missing required environment variables: {missing}")
        return None
    
    try:
        print(f"[INFO] Initializing LightRAG with workdir: {WORKDIR}")
        
        # Basic LightRAG configuration without custom Pinecone storage
        # Using default nano-vectordb for now (can add Pinecone later)
        _rag_instance = LightRAG(
            working_dir=WORKDIR,
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
        )
        
        print("[INFO] LightRAG instance initialized successfully")
        return _rag_instance
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize LightRAG: {e}")
        import traceback
        traceback.print_exc()
        return None


# =============================================================================
# Request/Response Models
# =============================================================================

class IngestRequest(BaseModel):
    """Request model for document ingestion."""
    text: str = Field(..., description="Document text content to ingest")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (source, filename, keywords, etc.)"
    )


class IngestResponse(BaseModel):
    """Response model for ingestion requests."""
    status: str
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    lightrag_available: bool
    workdir_exists: bool
    workdir_path: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class QueryRequest(BaseModel):
    """Request model for querying the knowledge graph."""
    query: str = Field(..., description="Query text")
    mode: str = Field(default="hybrid", description="Search mode: local, global, or hybrid")


class QueryResponse(BaseModel):
    """Response model for query results."""
    answer: str
    mode: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# Background Task: Document Ingestion
# =============================================================================

def process_ingest(text: str, metadata: Dict[str, Any]) -> None:
    """
    Background task to ingest document into knowledge graph.
    """
    rag = get_rag_instance()
    if rag is None:
        print("[ERROR] Cannot process ingestion - RAG not available")
        return
    
    try:
        source = metadata.get("source", "unknown")
        filename = metadata.get("filename", "unnamed")
        print(f"[INGEST START] Processing document: {filename} from {source}")
        start_time = datetime.utcnow()
        
        # Prepend metadata context if available
        context_prefix = ""
        if metadata.get("summary"):
            context_prefix += f"Summary: {metadata['summary']}\n\n"
        if metadata.get("keywords"):
            keywords = metadata["keywords"]
            if isinstance(keywords, list):
                keywords = ", ".join(keywords)
            context_prefix += f"Keywords: {keywords}\n\n"
        
        enriched_text = context_prefix + text if context_prefix else text
        
        # Insert into LightRAG
        rag.insert(enriched_text)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        print(f"[INGEST COMPLETE] {filename} processed in {elapsed:.1f}s")
        
    except Exception as e:
        print(f"[INGEST ERROR] Failed to process document: {e}")
        import traceback
        traceback.print_exc()


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check."""
    return await health_check()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    status = "ok" if LIGHTRAG_AVAILABLE else "degraded"
    return HealthResponse(
        status=status,
        lightrag_available=LIGHTRAG_AVAILABLE,
        workdir_exists=os.path.exists(WORKDIR),
        workdir_path=WORKDIR
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(req: IngestRequest, background_tasks: BackgroundTasks):
    """
    Ingest a document into the knowledge graph.
    Returns immediately while processing continues in background.
    """
    if not LIGHTRAG_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="LightRAG service not available - check logs for import errors"
        )
    
    if not req.text or len(req.text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Text content is required and must be at least 10 characters"
        )
    
    background_tasks.add_task(process_ingest, req.text, req.metadata)
    
    return IngestResponse(
        status="accepted",
        message="Procesamiento de grafo iniciado"
    )


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    """Query the knowledge graph."""
    rag = get_rag_instance()
    if rag is None:
        raise HTTPException(
            status_code=503,
            detail="LightRAG service not available"
        )
    
    if req.mode not in ["local", "global", "hybrid"]:
        raise HTTPException(
            status_code=400,
            detail="Mode must be 'local', 'global', or 'hybrid'"
        )
    
    try:
        answer = rag.query(req.query, param={"mode": req.mode})
        return QueryResponse(answer=answer, mode=req.mode)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}"
        )


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"[INFO] Starting LightRAG service on {host}:{port}")
    print(f"[INFO] Working directory: {WORKDIR}")
    print(f"[INFO] LightRAG available: {LIGHTRAG_AVAILABLE}")
    
    uvicorn.run(app, host=host, port=port)
