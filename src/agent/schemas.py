"""Pydantic models for PlaceGuard validation."""

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class PlaceQuery(BaseModel):
    """User input for place validation.
    
    Accepts natural language queries or raw LLM output about places.
    """

    query: str = Field(
        ..., 
        description="Natural language query or LLM output about a place",
        min_length=3,
        max_length=2000
    )
    context: Optional[dict[str, Any]] = Field(
        None,
        description="Additional context (city, country, preferences)"
    )
    lm_output: Optional[dict[str, Any]] = Field(
        None,
        description="Raw LLM JSON response if provided"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "Rooftop bar in Gangnam under $20 cocktails",
                    "context": {"city": "Seoul", "country": "KR"}
                }
            ]
        }
    )


class ValidationIssue(BaseModel):
    """A single validation issue or flag."""
    
    severity: Literal["info", "warning", "error"]
    field: str = Field(..., description="Field with the issue")
    message: str = Field(..., description="Human-readable issue description")
    suggestion: Optional[str] = Field(None, description="Suggested fix or clarification")


class PlaceDetails(BaseModel):
    """Enriched place details returned from validation."""
    
    address: str
    city: Optional[str] = None
    country: Optional[str] = None
    hours: Optional[str] = Field(None, description="Operating hours (e.g., 'Mon-Sun 6PM-2AM')")
    price_tier: Optional[str] = Field(
        None, 
        description="Price tier: '$', '$$', '$$$', or '$$$$'"
    )
    category: str = Field(default="Unknown", description="Business category")
    reviews_summary: Optional[str] = Field(None, description="Summary of customer reviews")
    average_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    data_freshness: Optional[Literal["current", "recent", "stale"]] = Field(
        "current",
        description="How fresh the data is"
    )
    
    # Additional enrichment
    safety_indicators: Optional[dict[str, Any]] = None
    tourist_friendly: Optional[bool] = None
    wheelchair_accessible: Optional[bool] = None


class ValidationResult(BaseModel):
    """Complete validation result matching VOYGR's Business Validation API."""
    
    # Identification
    place_id: str = Field(..., description="Unique place identifier")
    name: str = Field(..., description="Place name")
    
    # Validation status
    status: Literal["valid", "uncertain", "invalid"] = Field(
        ..., 
        description="Overall validation status"
    )
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Confidence score 0.0-1.0"
    )
    
    # Validation fields
    exists: bool = Field(..., description="Place exists in database/external sources")
    operating: bool = Field(..., description="Place is currently operating")
    price_verified: bool = Field(..., description="Price claims have been verified")
    safety_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Safety/trust score for the place"
    )
    
    # Enrichment
    details: PlaceDetails = Field(..., description="Enriched place details")
    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="Any validation issues or flags"
    )
    
    # Traceability
    reasoning_chain: list[str] = Field(
        ...,
        description="Step-by-step reasoning from the agent"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_used: str = Field(default="gpt-4", description="LLM model used")
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "place_id": "gangnam-rooftop-22",
                    "name": "Sky Lounge Gangnam",
                    "status": "valid",
                    "confidence": 0.87,
                    "exists": True,
                    "operating": True,
                    "price_verified": True,
                    "safety_score": 0.92,
                    "details": {
                        "address": "123 Gangnam-daero, Seoul",
                        "hours": "Mon-Sun 6PM-2AM",
                        "price_tier": "$$",
                        "category": "Rooftop Bar"
                    },
                    "reasoning_chain": [
                        "Searching for rooftop bars in Gangnam...",
                        "Found Sky Lounge Gangnam",
                        "Verified operating hours",
                        "Confirmed cocktail prices under $20"
                    ]
                }
            ]
        }
    )


class BenchmarkScenario(BaseModel):
    """A test scenario from VOYGR's benchmark suite."""
    
    scenario_id: str = Field(..., description="Unique scenario identifier")
    name: str = Field(..., description="Human-readable scenario name")
    description: str = Field(..., description="Scenario description")
    query: str = Field(..., description="Input query to validate")
    context: Optional[dict[str, Any]] = None
    
    # Expected outcomes
    expected_status: Literal["valid", "uncertain", "invalid"]
    expected_confidence_min: float = Field(ge=0.0, le=1.0)
    expected_place_name: Optional[str] = None
    expected_issues_count: int = Field(ge=0, le=10)
    
    # Grading
    test_category: Literal[
        "valid_clear",
        "ambiguous",
        "hallucinated",
        "stale_data",
        "edge_case",
        "international"
    ]


class ValidationHistory(BaseModel):
    """Summary of a validation for history tracking."""
    
    query: str
    status: Literal["valid", "uncertain", "invalid"]
    confidence: float
    place_name: Optional[str]
    timestamp: datetime
    model_used: str


class APIResponse(BaseModel):
    """Standard API response wrapper."""
    
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "data": {"status": "valid"},
                    "error": None
                }
            ]
        }
    )
