"""
Main FastAPI application - AI Security Control Plane
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

# Load .env file FIRST - CRITICAL!
from dotenv import load_dotenv
load_dotenv()

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from control_plane.api.init_db import init_db

# Configure stdlib logging first
logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,
)

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Load config from .env
TRACING_ENABLED = os.getenv("TRACING_ENABLED", "false").lower() == "true"

# Log what was loaded
logger.info("=== CONTROL PLANE CONFIGURATION ===")
logger.info("control_plane_config", tracing_enabled=TRACING_ENABLED)
logger.info("raw_env_values", TRACING_ENABLED_raw=os.getenv("TRACING_ENABLED"))


# =============================================================================
# OPENTELEMETRY SETUP
# =============================================================================

def setup_telemetry():
    """Configure OpenTelemetry tracing"""
    if not TRACING_ENABLED:
        logger.info("tracing_disabled")
        return
    
    try:
        # Only set if not already set
        if trace.get_tracer_provider().__class__.__name__ == "ProxyTracerProvider":
            provider = TracerProvider()
            
            # Use console exporter for simplicity
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
            trace.set_tracer_provider(provider)
            
            logger.info("telemetry_configured", exporter="console")
    except Exception as e:
        logger.warning("telemetry_setup_failed", error=str(e))


# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown logic"""
    # Startup
    logger.info("starting_control_plane")
    
    # Initialize database
    init_db()
    
    # Setup telemetry
    setup_telemetry()
    
    yield
    
    # Shutdown
    logger.info("shutting_down_control_plane")


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title="AI Security Control Plane",
    description="Governance for AI agents aligned with NIST AI RMF and OWASP",
    version="1.0.0",
    lifespan=lifespan,
)

# Instrument FastAPI with OpenTelemetry
if TRACING_ENABLED:
    FastAPIInstrumentor.instrument_app(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-security-control-plane",
        "version": "1.0.0",
        "tracing_enabled": TRACING_ENABLED
    }


@app.get("/")
async def root():
    return {
        "service": "AI Security Control Plane",
        "framework_alignment": {
            "nist_ai_rmf": ["Govern", "Map", "Measure", "Manage"],
            "owasp": "Agentic SecOps Lifecycle"
        },
        "docs": "/docs",
        "tracing_enabled": TRACING_ENABLED
    }


# Import and include routers
from control_plane.api import routes_agents, routes_tools, routes_policies
from control_plane.api import routes_evidence, routes_posture, routes_eval, routes_rag

app.include_router(routes_agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(routes_tools.router, prefix="/api/tools", tags=["Tools"])
app.include_router(routes_policies.router, prefix="/api/policies", tags=["Policies"])
app.include_router(routes_evidence.router, prefix="/api/evidence", tags=["Evidence"])
app.include_router(routes_posture.router, prefix="/api/posture", tags=["Posture"])
app.include_router(routes_eval.router, prefix="/api/eval", tags=["Evaluation"])
app.include_router(routes_rag.router, prefix="/api/rag", tags=["RAG Security"])


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("control_plane.api.main:app", host=host, port=port, reload=True)