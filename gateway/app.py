"""
Control Plane Gateway Service
Handles ingress requests, applies DLP, enforces tool allowlists,
interfaces with LLMs and RAG systems, and logs events to the control plane.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import re
import uuid
from datetime import datetime

app = FastAPI()

# Configuration
CONTROL_PLANE_URL = "http://localhost:8000"
LLM_URL = "http://localhost:11434"  # Ollama

# ============================================================================
# DLP PATTERNS
# ============================================================================

DLP_PATTERNS = {
    "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "PHONE": r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b',
    "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
    "CREDIT_CARD": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
}


def apply_dlp_redaction(text: str) -> tuple[str, List[str]]:
    """Apply DLP redaction to text"""
    redacted = text
    redactions_applied = []
    
    for pii_type, pattern in DLP_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            redacted = re.sub(pattern, f"[{pii_type}_REDACTED]", redacted)
            redactions_applied.extend([pii_type] * len(matches))
    
    return redacted, redactions_applied


# ============================================================================
# REQUEST MODELS
# ============================================================================

class IngressRequest(BaseModel):
    prompt: str
    actor: str
    agent_id: int
    tool_requests: Optional[List[Dict[str, Any]]] = None


class RAGIngressRequest(BaseModel):
    prompt: str
    actor: str
    agent_id: int
    use_rag: bool = True
    k: int = 3


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_agent(agent_id: int) -> Dict:
    """Fetch agent from control plane"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CONTROL_PLANE_URL}/api/agents/{agent_id}")
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Agent not found")
        return response.json()


async def check_tool_allowlist(agent_id: int, tool_name: str) -> bool:
    """Check if tool is allowed for agent"""
    agent = await get_agent(agent_id)
    allowed_tools = agent.get("allowed_tools", [])
    return tool_name in allowed_tools


async def query_rag(query: str, agent_id: int, k: int = 3) -> List[Dict]:
    """Query RAG system"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{CONTROL_PLANE_URL}/api/rag/query",
                json={"query": query, "agent_id": agent_id, "k": k}
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("chunks", [])
            return []
        except Exception as e:
            print(f"RAG query error: {e}")
            return []


async def call_llm(prompt: str, model: str = "llama3.2:1b") -> Dict:
    """Call Ollama LLM"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{LLM_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            if response.status_code == 200:
                result = response.json()
                return {
                    "response": result.get("response", ""),
                    "tokens": result.get("eval_count", 0)
                }
            return {"response": "Error generating response", "tokens": 0}
        except Exception as e:
            return {"response": f"LLM error: {str(e)}", "tokens": 0}


async def log_event(event_type: str, agent_id: int, actor: str, trace_id: str, metadata: Dict):
    """Log event to control plane"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{CONTROL_PLANE_URL}/api/evidence",
                json={
                    "event_type": event_type,
                    "agent_id": agent_id,
                    "actor": actor,
                    "trace_id": trace_id,
                    "metadata": metadata
                }
            )
        except Exception as e:
            print(f"Event logging error: {e}")


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
def health():
    return {"status": "healthy", "service": "gateway"}


@app.post("/ingress")
async def ingress(request: IngressRequest):
    """Main ingress with DLP and tool enforcement"""
    
    trace_id = uuid.uuid4().hex
    start_time = datetime.utcnow()
    
    # 1. Apply DLP to prompt
    redacted_prompt, redactions = apply_dlp_redaction(request.prompt)
    
    # 2. Check tool allowlist if tools requested
    if request.tool_requests:
        for tool_req in request.tool_requests:
            tool_name = tool_req.get("tool")
            if tool_name:
                allowed = await check_tool_allowlist(request.agent_id, tool_name)
                if not allowed:
                    # Log policy violation
                    await log_event(
                        "tool_denied",
                        request.agent_id,
                        request.actor,
                        trace_id,
                        {
                            "tool": tool_name,
                            "reason": "not_in_allowlist",
                            "prompt": redacted_prompt
                        }
                    )
                    return {
                        "response": f"Access denied: Tool '{tool_name}' not allowed for this agent",
                        "model": "policy_engine",
                        "tokens_used": 0,
                        "redactions_applied": redactions,
                        "trace_id": trace_id,
                        "latency_ms": 0,
                        "policy_denied": True
                    }
    
    # 3. Call LLM with redacted prompt
    llm_result = await call_llm(redacted_prompt)
    
    # 4. Calculate latency
    latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    # 5. Apply DLP to response
    redacted_response, response_redactions = apply_dlp_redaction(llm_result["response"])
    all_redactions = redactions + response_redactions
    
    # 6. Log event
    await log_event(
        "llm_request",
        request.agent_id,
        request.actor,
        trace_id,
        {
            "model": "llama3.2:1b",
            "tokens_used": llm_result["tokens"],
            "redactions_count": len(all_redactions),
            "latency_ms": latency_ms,
            "tool_requests": len(request.tool_requests) if request.tool_requests else 0
        }
    )
    
    return {
        "response": redacted_response,
        "model": "llama3.2:1b",
        "tokens_used": llm_result["tokens"],
        "redactions_applied": all_redactions,
        "trace_id": trace_id,
        "latency_ms": latency_ms
    }


@app.post("/ingress/rag")
async def ingress_rag(request: RAGIngressRequest):
    """RAG-augmented ingress with DLP"""
    
    trace_id = uuid.uuid4().hex
    start_time = datetime.utcnow()
    
    # 1. Apply DLP to prompt
    redacted_prompt, redactions = apply_dlp_redaction(request.prompt)
    
    # 2. Query RAG if enabled
    rag_chunks = []
    if request.use_rag:
        rag_chunks = await query_rag(redacted_prompt, request.agent_id, request.k)
    
    # 3. Build augmented prompt
    if rag_chunks:
        context = "\n\n".join([chunk.get("text", "") for chunk in rag_chunks])
        augmented_prompt = f"Context:\n{context}\n\nQuestion: {redacted_prompt}\n\nAnswer based on the context above:"
    else:
        augmented_prompt = redacted_prompt
    
    # 4. Call LLM
    llm_result = await call_llm(augmented_prompt)
    
    # 5. Calculate latency
    latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    # 6. Apply DLP to response
    redacted_response, response_redactions = apply_dlp_redaction(llm_result["response"])
    all_redactions = redactions + response_redactions
    
    # 7. Log event
    await log_event(
        "llm_request_rag",
        request.agent_id,
        request.actor,
        trace_id,
        {
            "model": "llama3.2:1b",
            "tokens_used": llm_result["tokens"],
            "redactions_count": len(all_redactions),
            "rag_chunks_used": len(rag_chunks),
            "latency_ms": latency_ms
        }
    )
    
    return {
        "response": redacted_response,
        "model": "llama3.2:1b",
        "tokens_used": llm_result["tokens"],
        "redactions_applied": all_redactions,
        "rag_chunks": rag_chunks,
        "trace_id": trace_id,
        "latency_ms": latency_ms
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)