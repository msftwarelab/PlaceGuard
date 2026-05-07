"""Validation tools for PlaceGuard ReAct agent.

These are the tools the LangGraph agent can call to validate places.
Each tool represents a discrete validation step in the reasoning process.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from langchain_core.tools import tool

from agent.data_layer import (
    search_places,
    get_place_by_id,
    check_data_freshness,
    calculate_price_match,
)


@tool
def validate_place_existence(
    place_name: str,
    city: Optional[str] = None,
    country: Optional[str] = None
) -> str:
    """
    Check if a place exists in the validation database.
    
    Use this tool when you need to verify if a place actually exists.
    
    Args:
        place_name: Name of the place to search for
        city: Optional city to narrow search
        country: Optional country code (e.g. 'KR', 'JP', 'US')
    
    Returns:
        JSON string with place existence results and metadata
    """
    query = f"{place_name} {city or ''} {country or ''}".strip()
    results = search_places(query, city=city)
    
    if not results:
        return json.dumps({
            "exists": False,
            "confidence": 0.1,
            "message": f"No place found matching '{place_name}' in {city or 'the database'}",
            "suggestions": [],
        })
    
    best_match = results[0]
    
    # Calculate match confidence based on name similarity
    name_match = place_name.lower() in best_match["name"].lower()
    city_match = not city or city.lower() in best_match.get("city", "").lower()
    
    confidence = 0.9 if name_match and city_match else 0.6 if name_match else 0.4
    
    return json.dumps({
        "exists": True,
        "confidence": confidence,
        "place_id": best_match["id"],
        "name": best_match["name"],
        "city": best_match.get("city"),
        "address": best_match.get("address"),
        "category": best_match.get("category"),
        "verified": best_match.get("verified", False),
        "message": f"Found: {best_match['name']} in {best_match.get('city', 'unknown city')}",
        "all_results": [{"id": r["id"], "name": r["name"]} for r in results[:3]],
    })


@tool
def check_operating_hours(place_id: str) -> str:
    """
    Check if a place is currently operating and get its hours.
    
    Use this after validate_place_existence to check operational status.
    
    Args:
        place_id: The place ID from validate_place_existence
    
    Returns:
        JSON string with operating status and hours
    """
    place = get_place_by_id(place_id)
    
    if not place:
        return json.dumps({
            "operating": False,
            "hours": None,
            "message": f"Place ID '{place_id}' not found",
            "issues": ["Place not found in database"],
        })
    
    # Check data freshness
    last_updated = place.get("last_updated", datetime.utcnow().isoformat())
    freshness = check_data_freshness(last_updated)
    
    issues = []
    if freshness == "stale":
        issues.append(
            f"⚠️ Data is stale (last updated: {last_updated[:10]}). "
            "Operating hours may have changed."
        )
    elif freshness == "recent":
        issues.append(f"ℹ️ Data is {freshness} (last updated: {last_updated[:10]})")
    
    if not place.get("operating", False):
        issues.append("🚫 Place is permanently closed or temporarily suspended")
    
    return json.dumps({
        "operating": place.get("operating", False),
        "hours": place.get("hours"),
        "data_freshness": freshness,
        "last_updated": last_updated[:10],
        "issues": issues,
        "message": (
            f"{'Open' if place.get('operating') else 'CLOSED'}: "
            f"{place.get('hours') or 'No hours available'}"
        ),
    })


@tool
def verify_pricing(place_id: str, claimed_max_price: Optional[float] = None) -> str:
    """
    Verify the price range of a place against claims.
    
    Use this to validate price claims in user queries (e.g., "under $20 cocktails").
    
    Args:
        place_id: The place ID from validate_place_existence
        claimed_max_price: The maximum price claimed by user (in USD)
    
    Returns:
        JSON string with price verification results
    """
    place = get_place_by_id(place_id)
    
    if not place:
        return json.dumps({
            "price_verified": False,
            "price_tier": None,
            "issues": ["Place not found"],
        })
    
    price_range = place.get("price_range")
    price_tier = place.get("price_tier")
    price_verified, issues = calculate_price_match(place, claimed_max_price)
    
    return json.dumps({
        "price_verified": price_verified,
        "price_tier": price_tier,
        "price_range_usd": price_range,
        "claimed_max_price": claimed_max_price,
        "issues": issues,
        "message": (
            f"Price tier: {price_tier}. "
            f"Range: ${price_range['min_usd']}-${price_range['max_usd']} USD"
            if price_range
            else f"Price tier: {price_tier}. Exact range not available."
        ),
    })


@tool
def assess_safety_and_risk(place_id: str) -> str:
    """
    Assess safety and risk indicators for a place.
    
    Use this to evaluate if a place is suitable to recommend to travelers.
    
    Args:
        place_id: The place ID from validate_place_existence
    
    Returns:
        JSON string with safety assessment
    """
    place = get_place_by_id(place_id)
    
    if not place:
        return json.dumps({
            "safety_score": 0.0,
            "tourist_friendly": False,
            "issues": ["Place not found"],
        })
    
    safety_score = place.get("safety_score", 0.5)
    issues = []
    
    # Determine safety tier
    if safety_score >= 0.85:
        safety_tier = "excellent"
    elif safety_score >= 0.70:
        safety_tier = "good"
    elif safety_score >= 0.50:
        safety_tier = "moderate"
    else:
        safety_tier = "poor"
        issues.append("⚠️ Low safety score - recommend verification before suggesting")
    
    if not place.get("tourist_friendly"):
        issues.append("ℹ️ May not be optimized for international tourists")
    
    if not place.get("verified"):
        issues.append("⚠️ Place not officially verified in our database")
    
    return json.dumps({
        "safety_score": safety_score,
        "safety_tier": safety_tier,
        "tourist_friendly": place.get("tourist_friendly"),
        "verified": place.get("verified"),
        "average_rating": place.get("average_rating"),
        "review_count": place.get("review_count"),
        "issues": issues,
        "message": f"Safety: {safety_tier} ({safety_score:.0%}). "
                   f"Rating: {place.get('average_rating', 'N/A')}/5.0 "
                   f"({place.get('review_count', 0):,} reviews)",
    })


@tool
def enrich_place_data(place_id: str) -> str:
    """
    Enrich place data with contextual information.
    
    Use this after validation to add reviews summary, categories, and tags.
    This is the final enrichment step before generating the report.
    
    Args:
        place_id: The place ID from validate_place_existence
    
    Returns:
        JSON string with enriched place details
    """
    place = get_place_by_id(place_id)
    
    if not place:
        return json.dumps({
            "success": False,
            "message": "Place not found for enrichment",
        })
    
    return json.dumps({
        "success": True,
        "place_id": place_id,
        "name": place["name"],
        "category": place.get("category", "Unknown"),
        "address": place.get("address"),
        "city": place.get("city"),
        "country": place.get("country"),
        "tags": place.get("tags", []),
        "reviews_summary": place.get("reviews_summary"),
        "average_rating": place.get("average_rating"),
        "review_count": place.get("review_count"),
        "coordinates": place.get("coordinates"),
        "message": f"Successfully enriched data for {place['name']}",
    })


@tool
def lookup_similar_alternatives(
    query: str,
    city: Optional[str] = None,
    category: Optional[str] = None,
    max_price_usd: Optional[float] = None
) -> str:
    """
    Find alternative places when the primary result fails validation.
    
    Use this when the original place is closed, invalid, or doesn't meet criteria.
    
    Args:
        query: Original search query
        city: City to search in
        category: Business category to search for
        max_price_usd: Maximum price per item in USD
    
    Returns:
        JSON string with up to 3 alternative place suggestions
    """
    results = search_places(query, city=city, category=category, max_results=5)
    
    # Filter by operating status and price
    valid_alternatives = []
    for place in results:
        if not place.get("operating", False):
            continue
        
        if max_price_usd:
            price_range = place.get("price_range")
            if price_range and price_range.get("min_usd", 0) > max_price_usd:
                continue
        
        valid_alternatives.append({
            "place_id": place["id"],
            "name": place["name"],
            "category": place.get("category"),
            "price_tier": place.get("price_tier"),
            "hours": place.get("hours"),
            "safety_score": place.get("safety_score"),
            "average_rating": place.get("average_rating"),
        })
    
    if not valid_alternatives:
        return json.dumps({
            "found": False,
            "alternatives": [],
            "message": "No valid alternatives found",
        })
    
    return json.dumps({
        "found": True,
        "alternatives": valid_alternatives[:3],
        "message": f"Found {len(valid_alternatives)} valid alternatives",
    })


# Expose tools as a list for the agent to bind
VALIDATION_TOOLS = [
    validate_place_existence,
    check_operating_hours,
    verify_pricing,
    assess_safety_and_risk,
    enrich_place_data,
    lookup_similar_alternatives,
]
