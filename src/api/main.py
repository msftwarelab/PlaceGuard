"""PlaceGuard FastAPI backend.

Provides the REST API for the PlaceGuard validation service.

Endpoints:
    POST /validate-place   — Main validation endpoint
    GET  /history          — Recent validation history
    GET  /benchmarks       — Benchmark scenarios
    POST /run-benchmark    — Run all benchmark scenarios
    GET  /health           — Health check
"""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # Load .env before anything else

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.benchmarks import BENCHMARK_SCENARIOS
from agent.data_layer import get_validation_history, save_validation
from agent.graph import run_validation
from agent.schemas import (
    APIResponse,
    BenchmarkScenario,
    PlaceQuery,
    ValidationHistory,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# Logging setup using structlog for structured, JSON-compatible logging
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger("placeguard.api")


# ---------------------------------------------------------------------------
# In-memory rate limiting (production: use Redis)
# ---------------------------------------------------------------------------
_request_counts: dict[str, list[float]] = {}


def check_rate_limit(client_ip: str, limit: int = 100, window: int = 60) -> bool:
    """Check if a client IP is within the rate limit.
    
    Args:
        client_ip: Client IP address
        limit: Maximum requests per window
        window: Window size in seconds
    
    Returns:
        True if within limit, False if exceeded
    """
    now = time.time()
    cutoff = now - window
    
    if client_ip not in _request_counts:
        _request_counts[client_ip] = []
    
    # Remove timestamps outside the window
    _request_counts[client_ip] = [t for t in _request_counts[client_ip] if t > cutoff]
    
    if len(_request_counts[client_ip]) >= limit:
        return False
    
    _request_counts[client_ip].append(now)
    return True


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    logger.info("placeguard_api_starting", version="0.1.0")
    yield
    logger.info("placeguard_api_stopping")


app = FastAPI(
    title="PlaceGuard API",
    description=(
        "VOYGR's production-grade place validation service. "
        "Validates LLM-generated place recommendations using a ReAct agent."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow Streamlit dashboard and external consumers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware: request logging + rate limiting
# ---------------------------------------------------------------------------

@app.middleware("http")
async def logging_and_rate_limit_middleware(request: Request, call_next):
    """Log every request and enforce rate limits."""
    request_id = str(uuid.uuid4())[:8]
    client_ip = request.client.host if request.client else "unknown"
    start_time = time.time()
    
    # Rate limiting (skip for health checks)
    if request.url.path != "/health":
        if not check_rate_limit(client_ip, limit=100, window=60):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error": "Rate limit exceeded. Max 100 requests per minute.",
                    "retry_after": 60,
                },
            )
    
    # Process request
    response = await call_next(request)
    
    # Log request
    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(
        "http_request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client_ip=client_ip,
    )
    
    # Add useful response headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration_ms}ms"
    
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Health check endpoint for uptime monitoring and Railway health probes."""
    return {
        "status": "healthy",
        "service": "PlaceGuard API",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post(
    "/validate-place",
    response_model=ValidationResult,
    tags=["Validation"],
    summary="Validate a place recommendation",
    description=(
        "Accepts a natural language query or raw LLM output about a place. "
        "Returns a structured validation result matching VOYGR's Business Validation API."
    ),
)
async def validate_place(query: PlaceQuery, request: Request) -> ValidationResult:
    """
    Main validation endpoint.
    
    The PlaceGuard ReAct agent will:
    1. Parse the query to identify the place
    2. Validate existence, operating status, and pricing
    3. Assess safety and enrich with contextual data
    4. Return a structured JSON result
    
    Example:
        POST /validate-place
        {
            "query": "Rooftop bar in Gangnam under $20 cocktails",
            "context": {"city": "Seoul", "country": "KR"}
        }
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    
    logger.info(
        "validation_started",
        request_id=request_id,
        query=query.query[:100],
    )
    
    try:
        result = run_validation(query)
        
        # Persist to history
        save_validation({
            "query": query.query,
            "status": result.status,
            "confidence": result.confidence,
            "place_name": result.name,
            "timestamp": result.timestamp.isoformat(),
            "model_used": result.model_used,
        })
        
        logger.info(
            "validation_completed",
            request_id=request_id,
            place_name=result.name,
            status=result.status,
            confidence=result.confidence,
        )
        
        return result
    
    except ValueError as e:
        logger.warning("validation_input_error", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    except RuntimeError as e:
        logger.error("validation_agent_error", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}",
        )
    
    except Exception as e:
        logger.exception("validation_unexpected_error", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        )


@app.get(
    "/history",
    response_model=list[ValidationHistory],
    tags=["History"],
    summary="Get recent validation history",
)
async def get_history(limit: int = 20) -> list[dict]:
    """
    Get the most recent validation results.
    
    Returns up to `limit` validations ordered by most recent first.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100",
        )
    
    history = get_validation_history(limit=limit)
    return history


@app.get(
    "/benchmarks",
    response_model=list[BenchmarkScenario],
    tags=["Benchmarks"],
    summary="Get benchmark test scenarios",
    description="Returns VOYGR's 6 benchmark scenarios for testing the PlaceGuard agent.",
)
async def get_benchmarks() -> list[BenchmarkScenario]:
    """Get all benchmark test scenarios."""
    return BENCHMARK_SCENARIOS


@app.post(
    "/run-benchmark",
    tags=["Benchmarks"],
    summary="Run all benchmark scenarios",
    description=(
        "Executes all 6 VOYGR benchmark scenarios and returns pass/fail results. "
        "Useful for regression testing and CTO demos."
    ),
)
async def run_benchmarks() -> dict:
    """
    Run all benchmark scenarios and return scored results.
    
    This demonstrates the agent's quality on known test cases.
    """
    results = []
    passed = 0
    
    for scenario in BENCHMARK_SCENARIOS:
        try:
            query = PlaceQuery(
                query=scenario.query,
                context=scenario.context,
            )
            result = run_validation(query)
            
            # Grade the result
            status_pass = result.status == scenario.expected_status
            confidence_pass = result.confidence >= scenario.expected_confidence_min
            issues_pass = len(result.issues) >= scenario.expected_issues_count
            
            test_passed = status_pass and confidence_pass
            if test_passed:
                passed += 1
            
            results.append({
                "scenario_id": scenario.scenario_id,
                "name": scenario.name,
                "passed": test_passed,
                "expected_status": scenario.expected_status,
                "actual_status": result.status,
                "expected_confidence_min": scenario.expected_confidence_min,
                "actual_confidence": round(result.confidence, 3),
                "status_pass": status_pass,
                "confidence_pass": confidence_pass,
                "place_found": result.name,
                "issues_count": len(result.issues),
            })
        
        except Exception as e:
            results.append({
                "scenario_id": scenario.scenario_id,
                "name": scenario.name,
                "passed": False,
                "error": str(e),
            })
    
    score = round(passed / len(BENCHMARK_SCENARIOS) * 100, 1)
    
    logger.info("benchmark_run_completed", score=score, passed=passed, total=len(BENCHMARK_SCENARIOS))
    
    return {
        "score": score,
        "passed": passed,
        "total": len(BENCHMARK_SCENARIOS),
        "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D",
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }
